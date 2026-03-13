from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable

from app.pipeline.lexicon_builder import LexiconArtifact
from app.pipeline.line_transcriber import LineOcrCandidate, LinePrediction, PanelTranscription
from app.pipeline.measurement_decoder import (
    canonicalize_exact_line,
    label_family_key,
    line_pattern,
    parse_measurement_line,
)


@dataclass(frozen=True)
class RankedCandidate:
    candidate: LineOcrCandidate
    score: float
    signals: dict[str, float] = field(default_factory=dict)


class LexiconReranker:
    def __init__(
        self,
        lexicon: LexiconArtifact,
        *,
        low_confidence_threshold: float = 0.72,
    ) -> None:
        self.lexicon = lexicon
        self.low_confidence_threshold = float(low_confidence_threshold)

    def rank_candidates(
        self,
        candidates: Iterable[LineOcrCandidate],
        *,
        line_order: int,
        previous_line: str | None = None,
    ) -> list[RankedCandidate]:
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            signals = self._score_candidate(candidate, line_order=line_order, previous_line=previous_line)
            score = sum(signals.values())
            ranked.append(RankedCandidate(candidate=candidate, score=score, signals=signals))
        ranked.sort(key=lambda item: (item.score, item.candidate.confidence, len(item.candidate.text)), reverse=True)
        return ranked

    def rerank_panel(self, panel: PanelTranscription) -> PanelTranscription:
        rebuilt_lines: list[LinePrediction] = []
        previous_line: str | None = None
        disagreement_count = 0

        for line in panel.lines:
            ranked = self.rank_candidates(line.candidates or (self._as_candidate(line),), line_order=line.order, previous_line=previous_line)
            best = ranked[0].candidate if ranked else self._as_candidate(line)
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
                    uncertain=(ranked[0].score if ranked else 0.0) < self.low_confidence_threshold,
                    candidates=line.candidates or (best,),
                    metadata={
                        **line.metadata,
                        "rerank_score": ranked[0].score if ranked else 0.0,
                        "rerank_signals": ranked[0].signals if ranked else {},
                    },
                )
            )
            previous_line = chosen_text

        combined_text = "\n".join(line.text for line in rebuilt_lines if line.text).strip()
        uncertain_count = sum(1 for line in rebuilt_lines if line.uncertain)
        return PanelTranscription(
            lines=tuple(rebuilt_lines),
            combined_text=combined_text,
            uncertain_line_count=uncertain_count,
            fallback_invocations=panel.fallback_invocations,
            engine_disagreement_count=max(panel.engine_disagreement_count, disagreement_count),
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
        }

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
