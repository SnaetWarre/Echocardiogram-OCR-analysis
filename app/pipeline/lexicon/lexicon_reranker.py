from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from app.pipeline.lexicon.lexicon_builder import LexiconArtifact, NumericStats
from app.pipeline.transcription.line_transcriber import LineOcrCandidate, LinePrediction, PanelTranscription
from app.pipeline.measurements.measurement_decoder import (
    canonicalize_exact_line,
    label_family_key,
    line_pattern,
    normalize_unit,
    parse_measurement_line,
)


@dataclass(frozen=True)
class RankedCandidate:
    candidate: LineOcrCandidate
    score: float
    signals: dict[str, float] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class PanelChoice:
    line: LinePrediction
    ranked: RankedCandidate


@dataclass(frozen=True)
class _PanelBeamState:
    score: float
    previous_line: str | None = None
    seen_family_prefixes: frozenset[tuple[str, str]] = frozenset()
    seen_lines: frozenset[str] = frozenset()
    choices: tuple[PanelChoice, ...] = ()


class LexiconReranker:
    def __init__(
        self,
        lexicon: LexiconArtifact,
        *,
        low_confidence_threshold: float = 0.72,
        panel_beam_width: int = 6,
        panel_candidate_limit: int = 4,
    ) -> None:
        self.lexicon = lexicon
        self.low_confidence_threshold = float(low_confidence_threshold)
        self.panel_beam_width = max(1, int(panel_beam_width))
        self.panel_candidate_limit = max(1, int(panel_candidate_limit))
        self._family_transition_frequencies = self._build_family_transition_frequencies()

    def rank_candidates(
        self,
        candidates: Iterable[LineOcrCandidate],
        *,
        line_order: int,
        previous_line: str | None = None,
    ) -> list[RankedCandidate]:
        candidate_pool = self._augment_candidates(tuple(candidates), line_order=line_order)
        ranked: list[RankedCandidate] = []
        for candidate in candidate_pool:
            signals = self._score_candidate(candidate, line_order=line_order, previous_line=previous_line)
            score = sum(signals.values())
            ranked.append(RankedCandidate(candidate=candidate, score=score, signals=signals))
        ranked.sort(key=lambda item: (item.score, item.candidate.confidence, len(item.candidate.text)), reverse=True)
        return ranked

    def rerank_panel(self, panel: PanelTranscription) -> PanelTranscription:
        rebuilt_lines: list[LinePrediction] = []
        disagreement_count = 0

        for choice in self._select_panel_choices(panel):
            line = choice.line
            ranked_item = choice.ranked
            best = ranked_item.candidate
            chosen_text = canonicalize_exact_line(best.text)
            if canonicalize_exact_line(line.text) != chosen_text and len(line.candidates) > 1:
                disagreement_count += 1
            rebuilt_lines.append(
                LinePrediction(
                    order=line.order,
                    bbox=line.bbox,
                    text=chosen_text,
                    confidence=max(best.confidence, line.confidence),
                    engine_name=best.engine_name,
                    source=best.source,
                    uncertain=ranked_item.score < self.low_confidence_threshold,
                    manual_verify_required=line.manual_verify_required,
                    candidates=line.candidates or (best,),
                    metadata={
                        **line.metadata,
                        "rerank_score": ranked_item.score,
                        "rerank_signals": ranked_item.signals,
                    },
                )
            )

        combined_text = "\n".join(line.text for line in rebuilt_lines if line.text).strip()
        uncertain_count = sum(1 for line in rebuilt_lines if line.uncertain)
        return PanelTranscription(
            lines=tuple(rebuilt_lines),
            combined_text=combined_text,
            uncertain_line_count=uncertain_count,
            fallback_invocations=panel.fallback_invocations,
            engine_disagreement_count=max(panel.engine_disagreement_count, disagreement_count),
            fallback_accept_count=panel.fallback_accept_count,
            fallback_reject_count=panel.fallback_reject_count,
            manual_verify_line_count=panel.manual_verify_line_count,
        )

    def _score_candidate(
        self,
        candidate: LineOcrCandidate,
        *,
        line_order: int,
        previous_line: str | None,
    ) -> dict[str, float]:
        canonical = canonicalize_exact_line(candidate.text)
        decoded = parse_measurement_line(canonical)
        family = label_family_key(decoded.label)

        confidence_score = max(0.0, min(candidate.confidence, 1.0)) * 0.55
        exact_line_score = min(self.lexicon.exact_line_frequencies.get(canonical, 0), 6) * 0.1
        label_score = min(self.lexicon.label_frequencies.get(family, 0), 8) * 0.04 if family else 0.0
        order_score = 0.0
        if family:
            order_hits = self.lexicon.label_order_frequencies.get(family, {})
            order_score = min(order_hits.get(str(line_order + 1), 0), 4) * 0.05
        unit_score = 0.0
        if family and decoded.unit:
            unit_hits = self.lexicon.label_unit_frequencies.get(family, {})
            unit_score = min(unit_hits.get(decoded.unit, 0), 4) * 0.05
        pattern_score = min(self.lexicon.line_pattern_frequencies.get(line_pattern(canonical), 0), 4) * 0.03
        syntax_score = decoded.syntax_confidence * 0.2
        family_similarity = self._best_family_similarity(family) * 0.15 if family else 0.0
        order_consistency = self._order_consistency(previous_line, canonical) * 0.05 if previous_line else 0.0
        transition_score = self._transition_frequency_score(previous_line, canonical) if previous_line else 0.0
        measurement_shape = 0.0
        if decoded.label:
            measurement_shape += 0.08
        if decoded.value:
            measurement_shape += 0.08
        if decoded.unit:
            measurement_shape += 0.04
        source_bonus = 0.0
        if candidate.source == "fallback_multiview":
            source_bonus += 0.03
        elif candidate.source == "primary_multiview":
            source_bonus += 0.02

        return {
            "ocr_confidence": confidence_score,
            "exact_line_match": exact_line_score,
            "label_frequency": label_score,
            "order_frequency": order_score,
            "unit_frequency": unit_score,
            "pattern_frequency": pattern_score,
            "syntax": syntax_score,
            "family_similarity": family_similarity,
            "order_consistency": order_consistency,
            "transition_frequency": transition_score,
            "measurement_shape": measurement_shape,
            "source_bonus": source_bonus,
        }

    def _select_panel_choices(self, panel: PanelTranscription) -> tuple[PanelChoice, ...]:
        if not panel.lines:
            return ()

        beam = [_PanelBeamState(score=0.0)]
        for line in panel.lines:
            next_beam: list[_PanelBeamState] = []
            base_candidates = line.candidates or (self._as_candidate(line),)
            for state in beam:
                ranked_candidates = self.rank_candidates(
                    base_candidates,
                    line_order=line.order,
                    previous_line=state.previous_line,
                )
                if not ranked_candidates:
                    ranked_candidates = [
                        RankedCandidate(
                            candidate=self._as_candidate(line),
                            score=0.0,
                            signals={},
                        )
                    ]
                for ranked_item in ranked_candidates[: self.panel_candidate_limit]:
                    chosen_text = canonicalize_exact_line(ranked_item.candidate.text)
                    next_score = state.score + ranked_item.score
                    next_score += self._panel_repeat_penalty(
                        chosen_text,
                        seen_lines=state.seen_lines,
                        seen_family_prefixes=state.seen_family_prefixes,
                    )
                    family_prefix_key = self._family_prefix_key(chosen_text)
                    next_beam.append(
                        _PanelBeamState(
                            score=next_score,
                            previous_line=chosen_text or state.previous_line,
                            seen_family_prefixes=(
                                state.seen_family_prefixes
                                if family_prefix_key is None
                                else state.seen_family_prefixes | {family_prefix_key}
                            ),
                            seen_lines=(
                                state.seen_lines
                                if not chosen_text
                                else state.seen_lines | {chosen_text}
                            ),
                            choices=state.choices + (PanelChoice(line=line, ranked=ranked_item),),
                        )
                    )
            beam = sorted(beam + next_beam, key=lambda state: state.score, reverse=True)[: self.panel_beam_width]

        best_state = max(beam, key=lambda state: state.score, default=None)
        if best_state is None or len(best_state.choices) != len(panel.lines):
            return tuple(
                PanelChoice(
                    line=line,
                    ranked=RankedCandidate(
                        candidate=self._as_candidate(line),
                        score=0.0,
                        signals={},
                    ),
                )
                for line in panel.lines
            )
        return best_state.choices

    def _augment_candidates(
        self,
        candidates: tuple[LineOcrCandidate, ...],
        *,
        line_order: int,
    ) -> tuple[LineOcrCandidate, ...]:
        augmented = list(candidates)
        seen = {canonicalize_exact_line(candidate.text) for candidate in candidates}
        for candidate in candidates:
            for repaired in self._repair_candidates_from_lexicon(candidate, line_order=line_order):
                canonical = canonicalize_exact_line(repaired.text)
                if not canonical or canonical in seen:
                    continue
                augmented.append(repaired)
                seen.add(canonical)
        return tuple(augmented)

    def _repair_candidates_from_lexicon(
        self,
        candidate: LineOcrCandidate,
        *,
        line_order: int,
    ) -> tuple[LineOcrCandidate, ...]:
        repairs: list[LineOcrCandidate] = []
        family_repair = self._repair_candidate_from_lexicon(candidate, line_order=line_order)
        if family_repair is not None:
            repairs.append(family_repair)
        repairs.extend(self._repair_known_family_candidate(candidate, line_order=line_order))
        return tuple(repairs)

    def _repair_candidate_from_lexicon(
        self,
        candidate: LineOcrCandidate,
        *,
        line_order: int,
    ) -> LineOcrCandidate | None:
        decoded = parse_measurement_line(candidate.text)
        if decoded.value is None or decoded.unit is None or decoded.label is None:
            return None
        if label_family_key(decoded.label) in self.lexicon.label_frequencies:
            return None

        best_family = self._best_matching_family(decoded.label, decoded.unit, line_order=line_order)
        if best_family is None:
            return None
        family_name, similarity = best_family
        if similarity < 0.82:
            return None

        exemplar_lines = self.lexicon.label_family_lines.get(family_name, [])
        if not exemplar_lines:
            return None
        exemplar_decoded = parse_measurement_line(exemplar_lines[0])
        repaired_label = exemplar_decoded.label or decoded.label
        parts: list[str] = []
        if decoded.prefix:
            parts.append(decoded.prefix)
        elif exemplar_decoded.prefix and self._family_prefers_prefix(family_name):
            parts.append(exemplar_decoded.prefix)
        parts.append(repaired_label)
        parts.append(decoded.value)
        parts.append(decoded.unit)
        repaired_text = canonicalize_exact_line(" ".join(parts))
        if not repaired_text:
            return None
        return LineOcrCandidate(
            text=repaired_text,
            confidence=max(0.0, candidate.confidence - 0.04),
            engine_name=candidate.engine_name,
            view_name=f"{candidate.view_name}:lexicon_repair",
            source=f"{candidate.source}_lexicon_repair",
            tokens=candidate.tokens,
            metadata={
                **candidate.metadata,
                "lexicon_repair_family": family_name,
                "lexicon_repair_similarity": similarity,
                "lexicon_repair_from": candidate.text,
            },
        )

    def _repair_known_family_candidate(
        self,
        candidate: LineOcrCandidate,
        *,
        line_order: int,
    ) -> list[LineOcrCandidate]:
        decoded = parse_measurement_line(candidate.text)
        if decoded.label is None or decoded.value is None:
            return []

        family_name = label_family_key(decoded.label)
        if family_name not in self.lexicon.label_frequencies:
            return []
        exemplar_lines = self.lexicon.label_family_lines.get(family_name, [])
        if not exemplar_lines:
            return []
        exemplar_decoded = parse_measurement_line(exemplar_lines[0])
        repairs: list[LineOcrCandidate] = []

        repaired_prefix = decoded.prefix
        family_prefers_prefix = self._family_prefers_prefix(family_name)
        if decoded.prefix is None and exemplar_decoded.prefix and family_prefers_prefix:
            repaired_prefix = exemplar_decoded.prefix
        elif decoded.prefix is not None and not family_prefers_prefix:
            repaired_prefix = None

        preferred_unit = self._preferred_unit_for_family(family_name)
        normalized_unit = normalize_unit(decoded.unit)
        repaired_unit = decoded.unit
        if preferred_unit and decoded.unit and normalized_unit != preferred_unit:
            repaired_unit = preferred_unit

        scaled_value = self._scaled_value_repair(decoded.value, family_name)
        prefixed_value = None if scaled_value is not None else self._leading_digit_value_repair(decoded.value, family_name)
        repaired_value = (
            scaled_value
            if scaled_value is not None
            else prefixed_value if prefixed_value is not None else decoded.value
        )

        if (
            repaired_prefix != decoded.prefix
            or repaired_unit != decoded.unit
            or repaired_value != decoded.value
        ):
            repairs.append(
                self._build_repaired_candidate(
                    candidate,
                    prefix=repaired_prefix,
                    label=decoded.label,
                    value=repaired_value,
                    unit=repaired_unit,
                    tag="family_repair",
                    metadata={
                        "lexicon_prefix_source": repaired_prefix,
                        "lexicon_preferred_unit": repaired_unit,
                        "lexicon_scaled_value_from": decoded.value,
                    },
                )
            )

        return repairs

    def _preferred_unit_for_family(self, family_name: str) -> str | None:
        unit_hits = self.lexicon.label_unit_frequencies.get(family_name, {})
        if not unit_hits:
            return None
        best_unit, _count = max(unit_hits.items(), key=lambda item: item[1])
        normalized = normalize_unit(best_unit)
        return normalized or best_unit

    def _scaled_value_repair(self, value: str, family_name: str) -> str | None:
        stats = self.lexicon.label_value_stats.get(family_name)
        if stats is None:
            return None
        try:
            numeric_value = float(value)
        except ValueError:
            return None
        if self._value_within_expected_range(numeric_value, stats):
            return None
        for factor in (0.1, 10.0):
            scaled_value = numeric_value * factor
            if self._value_within_expected_range(scaled_value, stats):
                return self._format_scaled_value(value, scaled_value)
        return None

    def _leading_digit_value_repair(self, value: str, family_name: str) -> str | None:
        stats = self.lexicon.label_value_stats.get(family_name)
        if stats is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2 or not normalized.startswith("1") or normalized.startswith("1."):
            return None
        candidate_text = normalized[1:]
        if not candidate_text or candidate_text.startswith("."):
            return None
        try:
            numeric_value = float(candidate_text)
        except ValueError:
            return None
        if not self._value_within_expected_range(numeric_value, stats):
            return None
        return self._format_scaled_value(value, numeric_value)

    @staticmethod
    def _value_within_expected_range(value: float, stats: NumericStats) -> bool:
        lower = max(0.0, stats.min * 0.75)
        upper = max(stats.max * 1.25, stats.mean * 1.25)
        return lower <= value <= upper

    @staticmethod
    def _format_scaled_value(original: str, scaled_value: float) -> str:
        decimals = 0
        if "." in original:
            decimals = len(original.split(".", maxsplit=1)[1])
        elif not float(scaled_value).is_integer():
            decimals = 1
        formatted = f"{scaled_value:.{min(2, decimals)}f}"
        if decimals == 0:
            formatted = f"{scaled_value:.0f}"
        return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted

    @staticmethod
    def _build_repaired_candidate(
        candidate: LineOcrCandidate,
        *,
        prefix: str | None,
        label: str | None,
        value: str | None,
        unit: str | None,
        tag: str,
        metadata: dict[str, object],
    ) -> LineOcrCandidate:
        parts: list[str] = []
        if prefix:
            parts.append(prefix)
        if label:
            parts.append(label)
        if value:
            parts.append(value)
        if unit:
            parts.append(unit)
        repaired_text = canonicalize_exact_line(" ".join(parts))
        return LineOcrCandidate(
            text=repaired_text,
            confidence=max(0.0, candidate.confidence - 0.03),
            engine_name=candidate.engine_name,
            view_name=f"{candidate.view_name}:{tag}",
            source=f"{candidate.source}_{tag}",
            tokens=candidate.tokens,
            metadata={
                **candidate.metadata,
                **metadata,
                "lexicon_repair_tag": tag,
                "lexicon_repair_from": candidate.text,
            },
        )

    def _best_matching_family(self, label: str, unit: str, *, line_order: int) -> tuple[str, float] | None:
        label_key = label_family_key(label)
        best_family: str | None = None
        best_score = 0.0
        for family_name, known_lines in self.lexicon.label_family_lines.items():
            if not known_lines:
                continue
            exemplar_decoded = parse_measurement_line(known_lines[0])
            if exemplar_decoded.unit and exemplar_decoded.unit != unit:
                continue
            order_hits = self.lexicon.label_order_frequencies.get(family_name, {})
            order_bonus = 0.03 if order_hits.get(str(line_order + 1), 0) > 0 else 0.0
            similarity = SequenceMatcher(None, label_key, family_name).ratio() + order_bonus
            if similarity > best_score:
                best_family = family_name
                best_score = similarity
        if best_family is None:
            return None
        return best_family, best_score

    def _family_prefers_prefix(self, family_name: str) -> bool:
        exemplar_lines = self.lexicon.label_family_lines.get(family_name, [])
        if not exemplar_lines:
            return False
        exemplar_decoded = parse_measurement_line(exemplar_lines[0])
        return exemplar_decoded.prefix is not None

    def _build_family_transition_frequencies(self) -> dict[str, dict[str, int]]:
        grouped_lines: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for entry in self.lexicon.source_lines:
            if entry.order is None:
                continue
            canonical = canonicalize_exact_line(entry.text)
            if not canonical:
                continue
            grouped_lines[f"{entry.split}:{entry.file_name}"].append((entry.order, canonical))

        transitions: dict[str, Counter[str]] = defaultdict(Counter)
        for ordered_lines in grouped_lines.values():
            ordered_texts = [text for _order, text in sorted(ordered_lines, key=lambda item: item[0])]
            for previous_text, current_text in zip(ordered_texts, ordered_texts[1:], strict=False):
                previous_family = self._family_key(previous_text)
                current_family = self._family_key(current_text)
                if not previous_family or not current_family:
                    continue
                transitions[previous_family][current_family] += 1
        return {family: dict(counts) for family, counts in transitions.items()}

    def _transition_frequency_score(self, previous_line: str, current_line: str) -> float:
        previous_family = self._family_key(previous_line)
        current_family = self._family_key(current_line)
        if not previous_family or not current_family or previous_family == current_family:
            return 0.0
        hits = self._family_transition_frequencies.get(previous_family, {}).get(current_family, 0)
        return min(hits, 4) * 0.04

    def _best_family_similarity(self, family: str) -> float:
        if not family:
            return 0.0
        if family in self.lexicon.label_frequencies:
            return 1.0
        best = 0.0
        for known in self.lexicon.label_frequencies.keys():
            best = max(best, SequenceMatcher(None, family, known).ratio())
        return best

    def _order_consistency(self, previous_line: str, current_line: str) -> float:
        prev_decoded = parse_measurement_line(previous_line)
        curr_decoded = parse_measurement_line(current_line)
        if prev_decoded.prefix and curr_decoded.prefix:
            try:
                prev_idx = int(prev_decoded.prefix)
                curr_idx = int(curr_decoded.prefix)
            except ValueError:
                return 0.0
            return 1.0 if curr_idx >= prev_idx else 0.0
        return 0.0

    def _family_key(self, text: str) -> str:
        decoded = parse_measurement_line(text)
        return label_family_key(decoded.label)

    def _family_prefix_key(self, text: str) -> tuple[str, str] | None:
        decoded = parse_measurement_line(text)
        family = label_family_key(decoded.label)
        if not family:
            return None
        return family, decoded.prefix or ""

    @staticmethod
    def _panel_repeat_penalty(
        text: str,
        *,
        seen_lines: frozenset[str],
        seen_family_prefixes: frozenset[tuple[str, str]],
    ) -> float:
        if not text:
            return 0.0
        penalty = 0.0
        if text in seen_lines:
            penalty -= 0.25
        decoded = parse_measurement_line(text)
        family = label_family_key(decoded.label)
        if family and (family, decoded.prefix or "") in seen_family_prefixes:
            penalty -= 0.12
        return penalty

    @staticmethod
    def _as_candidate(line: LinePrediction) -> LineOcrCandidate:
        return LineOcrCandidate(
            text=line.text,
            confidence=line.confidence,
            engine_name=line.engine_name,
            view_name="selected",
            source=line.source,
            metadata=dict(line.metadata),
        )
