from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.pipeline.line_segmenter import SegmentationResult, SegmentedLine
from app.pipeline.measurement_decoder import KNOWN_UNITS, canonicalize_exact_line, normalize_unit, parse_measurement_line
from app.pipeline.ocr_engines import OcrEngine, OcrResult, OcrToken


def _empty_metadata() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class LineOcrCandidate:
    text: str
    confidence: float
    engine_name: str
    view_name: str
    source: str
    tokens: tuple[OcrToken, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True)
class LinePrediction:
    order: int
    bbox: tuple[int, int, int, int]
    text: str
    confidence: float
    engine_name: str
    source: str
    uncertain: bool
    candidates: tuple[LineOcrCandidate, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True)
class PanelTranscription:
    lines: tuple[LinePrediction, ...] = field(default_factory=tuple)
    combined_text: str = ""
    uncertain_line_count: int = 0
    fallback_invocations: int = 0
    engine_disagreement_count: int = 0


def crop_segment(image: np.ndarray, segment: SegmentedLine) -> np.ndarray:
    x, y, width, height = segment.bbox
    height_limit = int(image.shape[0])
    width_limit = int(image.shape[1])
    x1 = max(0, min(x, width_limit))
    y1 = max(0, min(y, height_limit))
    x2 = max(x1, min(x + width, width_limit))
    y2 = max(y1, min(y + height, height_limit))
    return image[y1:y2, x1:x2].copy()


def _normalize_text_lines(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()


def _candidate_from_result(
    *,
    result: OcrResult,
    source: str,
    view_name: str,
    metadata: dict[str, Any] | None = None,
) -> LineOcrCandidate:
    return LineOcrCandidate(
        text=_normalize_text_lines(result.text),
        confidence=float(result.confidence),
        engine_name=result.engine_name,
        view_name=view_name,
        source=source,
        tokens=tuple(result.tokens),
        metadata=dict(metadata or {}),
    )


class LineTranscriber:
    def __init__(
        self,
        *,
        uncertain_threshold: float = 0.72,
        disagreement_similarity_threshold: float = 0.8,
        fallback_quality_threshold: float = 0.72,
        preprocess_views: dict[str, Callable[[np.ndarray], np.ndarray]] | None = None,
    ) -> None:
        self.uncertain_threshold = float(uncertain_threshold)
        self.disagreement_similarity_threshold = float(disagreement_similarity_threshold)
        self.fallback_quality_threshold = float(fallback_quality_threshold)
        self.preprocess_views = preprocess_views or {}

    def transcribe(
        self,
        roi_image: np.ndarray,
        segmentation: SegmentationResult,
        *,
        primary_engine: OcrEngine,
        fallback_engine: OcrEngine | None = None,
    ) -> PanelTranscription:
        predictions: list[LinePrediction] = []
        fallback_invocations = 0
        disagreement_count = 0
        view_items = list(self.preprocess_views.items()) or [("default", lambda image: image)]
        default_view_name, default_preprocessor = view_items[0]
        alternate_views = view_items[1:]

        for segment in segmentation.lines:
            raw_crop = crop_segment(roi_image, segment)
            if raw_crop.size == 0:
                continue

            primary_crop = default_preprocessor(raw_crop)
            primary_result = primary_engine.extract(primary_crop)
            primary_candidate = _candidate_from_result(
                result=primary_result,
                source="primary",
                view_name=default_view_name,
                metadata={"segment_order": segment.order, "view": default_view_name},
            )
            candidates = [primary_candidate]
            should_try_extra_views = self._should_try_additional_views(segment, primary_candidate)

            if should_try_extra_views:
                for view_name, preprocessor in alternate_views:
                    primary_view_result = primary_engine.extract(preprocessor(raw_crop))
                    candidates.append(
                        _candidate_from_result(
                            result=primary_view_result,
                            source="primary_multiview",
                            view_name=view_name,
                            metadata={"segment_order": segment.order, "view": view_name},
                        )
                    )

            candidates = self._filter_candidates(candidates)

            best_primary_candidate = max(candidates, key=self._candidate_rank_key)
            best_primary_quality = self._candidate_quality(best_primary_candidate)
            needs_fallback = (
                best_primary_quality < self.fallback_quality_threshold
                or not best_primary_candidate.text
                or self._looks_like_junk(best_primary_candidate)
                or self._looks_like_value_only_measurement(segment, best_primary_candidate)
                or self._looks_like_malformed_measurement_layout(segment, best_primary_candidate)
            )
            if fallback_engine is not None and needs_fallback:
                fallback_crop = default_preprocessor(raw_crop)
                fallback_result = fallback_engine.extract(fallback_crop)
                fallback_candidate = _candidate_from_result(
                    result=fallback_result,
                    source="fallback",
                    view_name=default_view_name,
                    metadata={"segment_order": segment.order, "view": default_view_name},
                )
                candidates.append(fallback_candidate)
                fallback_invocations += 1
                if _normalize_for_similarity(primary_candidate.text) != _normalize_for_similarity(fallback_candidate.text):
                    disagreement_count += 1

                if should_try_extra_views:
                    for view_name, preprocessor in alternate_views:
                        fallback_view_result = fallback_engine.extract(preprocessor(raw_crop))
                        candidates.append(
                            _candidate_from_result(
                                result=fallback_view_result,
                                source="fallback_multiview",
                                view_name=view_name,
                                metadata={"segment_order": segment.order, "view": view_name},
                            )
                        )

                candidates = self._filter_candidates(candidates)
                best_candidate = max(candidates, key=self._candidate_rank_key)
                if _normalize_for_similarity(best_primary_candidate.text) != _normalize_for_similarity(best_candidate.text):
                    disagreement_count += 1

            chosen = max(candidates, key=self._candidate_rank_key)
            chosen_text = canonicalize_exact_line(chosen.text)
            uncertain = self._candidate_quality(chosen) < self.uncertain_threshold or not chosen_text.strip()
            predictions.append(
                LinePrediction(
                    order=segment.order,
                    bbox=segment.bbox,
                    text=chosen_text,
                    confidence=chosen.confidence,
                    engine_name=chosen.engine_name,
                    source=chosen.source,
                    uncertain=uncertain,
                    candidates=tuple(candidates),
                    metadata={
                        "segmentation_source": segment.metadata.get("source"),
                        "token_count": segment.metadata.get("token_count", 0),
                        "candidate_count": len(candidates),
                        "candidate_quality": self._candidate_quality(chosen),
                        "best_primary_quality": best_primary_quality,
                    },
                )
            )

        ordered = sorted(predictions, key=lambda item: item.order)
        combined_text = "\n".join(line.text for line in ordered if line.text).strip()
        uncertain_count = sum(1 for line in ordered if line.uncertain)
        return PanelTranscription(
            lines=tuple(ordered),
            combined_text=combined_text,
            uncertain_line_count=uncertain_count,
            fallback_invocations=fallback_invocations,
            engine_disagreement_count=disagreement_count,
        )

    def _should_try_additional_views(self, segment: SegmentedLine, primary_candidate: LineOcrCandidate) -> bool:
        token_count = int(segment.metadata.get("token_count", 0) or 0)
        if bool(segment.metadata.get("refined_split")):
            return True
        if token_count <= 1:
            return True
        lines = [line.strip() for line in primary_candidate.text.splitlines() if line.strip()]
        if len(lines) >= 3:
            return True
        if len(lines) == 2 and self._is_value_before_label(lines[0], lines[1]):
            return True
        return False

    def _filter_candidates(self, candidates: list[LineOcrCandidate]) -> list[LineOcrCandidate]:
        if len(candidates) <= 1:
            return candidates

        scored = [(candidate, self._candidate_quality(candidate)) for candidate in candidates if candidate.text.strip()]
        if not scored:
            return candidates[:1]

        best_quality = max(score for _candidate, score in scored)
        best_has_measurement = any(score >= 0.95 for _candidate, score in scored)
        filtered = [
            candidate
            for candidate, score in scored
            if score >= best_quality - 0.22 and (not best_has_measurement or score >= 0.45)
        ]
        return filtered or [max(scored, key=lambda item: item[1])[0]]

    def _candidate_rank_key(self, candidate: LineOcrCandidate) -> tuple[float, float, int, bool]:
        return (
            self._candidate_quality(candidate),
            candidate.confidence,
            len(candidate.text.strip()),
            candidate.source.startswith("primary"),
        )

    def _candidate_quality(self, candidate: LineOcrCandidate) -> float:
        canonical = canonicalize_exact_line(candidate.text)
        decoded = parse_measurement_line(canonical)
        score = 0.0
        if canonical:
            score += 0.1
        score += max(0.0, min(candidate.confidence, 1.0)) * 0.15
        score += decoded.syntax_confidence * 0.2
        if decoded.label:
            score += 0.15
        if decoded.value:
            score += 0.15
        known_unit = normalize_unit(decoded.unit) if decoded.unit else None
        if known_unit in KNOWN_UNITS:
            score += 0.1
        if decoded.is_measurement:
            score += 0.35
        if decoded.unit and known_unit not in KNOWN_UNITS:
            score -= 0.18
        score -= self._noise_penalty(canonical)
        return score

    def _looks_like_junk(self, candidate: LineOcrCandidate) -> bool:
        canonical = canonicalize_exact_line(candidate.text)
        decoded = parse_measurement_line(canonical)
        if not canonical:
            return True
        if decoded.is_measurement:
            return False
        if self._noise_penalty(canonical) >= 0.12:
            return True
        known_unit = normalize_unit(decoded.unit) if decoded.unit else None
        if decoded.unit and known_unit not in KNOWN_UNITS:
            return True
        letters = sum(1 for char in canonical if char.isalpha())
        digits = sum(1 for char in canonical if char.isdigit())
        return letters + digits < 4

    def _looks_like_value_only_measurement(self, segment: SegmentedLine, candidate: LineOcrCandidate) -> bool:
        token_count = int(segment.metadata.get("token_count", 0) or 0)
        if token_count > 1:
            return False
        canonical = canonicalize_exact_line(candidate.text)
        decoded = parse_measurement_line(canonical)
        return decoded.value is not None and "missing_label" in decoded.uncertain_reasons

    def _looks_like_malformed_measurement_layout(self, segment: SegmentedLine, candidate: LineOcrCandidate) -> bool:
        token_count = int(segment.metadata.get("token_count", 0) or 0)
        if token_count > 1:
            return False
        canonical = canonicalize_exact_line(candidate.text)
        if not canonical:
            return False
        if re.search(r"\b(?:cm|mm|ml|m/s|mmHg|%)\s+[-+]?\d+(?:[.,]\d+)?$", canonical, flags=re.IGNORECASE):
            return True
        lines = [line.strip() for line in canonical.splitlines() if line.strip()]
        if len(lines) >= 2:
            first = lines[0]
            last = lines[-1]
            if re.search(r"\b(?:cm|mm|ml|m/s|mmHg|%)\b", first, flags=re.IGNORECASE) and re.search(r"\d", last):
                return True
            if re.search(r"[A-Za-z]", first) and re.fullmatch(r"(?:cm|mm|ml|m/s|mmHg|%)(?:\s+[-+]?\d+(?:[.,]\d+)?)?", last, flags=re.IGNORECASE):
                return True
        decoded = parse_measurement_line(canonical)
        if decoded.label and decoded.unit and decoded.value:
            label_index = canonical.find(decoded.label)
            unit_index = canonical.find(decoded.unit)
            value_index = canonical.find(decoded.value)
            if unit_index != -1 and value_index != -1 and unit_index < value_index:
                return True
            if label_index != -1 and value_index != -1 and unit_index != -1 and not (label_index <= value_index <= unit_index):
                return True
            if label_index != -1 and unit_index != -1 and value_index == -1:
                return True
        return False

    @staticmethod
    def _noise_penalty(text: str) -> float:
        if not text:
            return 0.2
        allowed = sum(1 for char in text if char.isalnum() or char.isspace() or char in "%'./-()")
        disallowed_ratio = 1.0 - (allowed / max(1, len(text)))
        repeated_punct = len(re.findall(r"[._\-=]{3,}", text))
        return disallowed_ratio * 0.2 + repeated_punct * 0.05

    @staticmethod
    def _is_value_before_label(first_line: str, second_line: str) -> bool:
        first_has_letters = bool(re.search(r"[A-Za-z]", first_line))
        second_has_letters = bool(re.search(r"[A-Za-z]", second_line))
        first_starts_value = bool(re.match(r"^[^A-Za-z]*[-+]?\d", first_line.strip()))
        return first_starts_value and second_has_letters and not first_has_letters


def _normalize_for_similarity(text: str) -> str:
    return " ".join(text.lower().split())
