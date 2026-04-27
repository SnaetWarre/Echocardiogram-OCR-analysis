from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.pipeline.layout.line_segmenter import SegmentationResult, SegmentedLine
from app.pipeline.measurements.measurement_decoder import KNOWN_UNITS, canonicalize_exact_line, normalize_unit, parse_measurement_line
from app.pipeline.ocr.char_fallback import CharFallbackClassifier
from app.pipeline.ocr.ocr_engines import OcrEngine, OcrResult, OcrToken
from app.pipeline.transcription.char_slice_ocr_experimental import per_char_slice_ocr_line
from app.pipeline.transcription.vertical_slicer import slice_line_into_vertical_slices


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
    manual_verify_required: bool = False
    candidates: tuple[LineOcrCandidate, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True)
class PanelTranscription:
    lines: tuple[LinePrediction, ...] = field(default_factory=tuple)
    combined_text: str = ""
    uncertain_line_count: int = 0
    fallback_invocations: int = 0
    engine_disagreement_count: int = 0
    fallback_accept_count: int = 0
    fallback_reject_count: int = 0
    manual_verify_line_count: int = 0


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
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filtered = [line for line in lines if not _looks_like_filler_line(line)]
    chosen = filtered or lines[:1]
    normalized = "\n".join(chosen[:3]).strip()
    return normalized[:160]


def _looks_like_filler_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if all(char in {"_", ".", "-", "/", " ", "~"} for char in stripped):
        return True
    alnum_count = sum(1 for char in stripped if char.isalnum())
    punctuation_count = sum(1 for char in stripped if not char.isalnum() and not char.isspace())
    if alnum_count == 0:
        return True
    return alnum_count <= 2 and punctuation_count >= max(2, alnum_count)


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
        char_fallback_enabled: bool = False,
        char_fallback_classifier: CharFallbackClassifier | None = None,
        char_fallback_min_split_confidence: float = 0.55,
        char_retry_confidence_threshold: float = 0.7,
        char_retry_min_char_confidence: float = 0.55,
        preprocess_views: dict[str, Callable[[np.ndarray], np.ndarray]] | None = None,
    ) -> None:
        self.uncertain_threshold = float(uncertain_threshold)
        self.disagreement_similarity_threshold = float(disagreement_similarity_threshold)
        self.fallback_quality_threshold = float(fallback_quality_threshold)
        self.char_fallback_enabled = bool(char_fallback_enabled)
        self.char_fallback_classifier = char_fallback_classifier
        self.char_fallback_min_split_confidence = float(char_fallback_min_split_confidence)
        self.char_retry_confidence_threshold = float(char_retry_confidence_threshold)
        self.char_retry_min_char_confidence = float(char_retry_min_char_confidence)
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
        fallback_accept_count = 0
        fallback_reject_count = 0
        manual_verify_line_count = 0
        view_items = list(self.preprocess_views.items()) or [("default", lambda image: image)]
        default_view_name, default_preprocessor = view_items[0]
        alternate_views = view_items[1:]

        for segment in segmentation.lines:
            raw_crop = crop_segment(roi_image, segment)
            if raw_crop.size == 0:
                continue

            split_result = slice_line_into_vertical_slices(raw_crop)
            expected_char_count = int(split_result.expected_char_count)
            split_confidence = float(split_result.confidence)

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
            primary_char_count = self._predicted_char_count(best_primary_candidate.text)
            primary_char_count_ok = expected_char_count <= 0 or primary_char_count == expected_char_count
            fallback_disagreement = False
            needs_fallback = (
                best_primary_quality < self.fallback_quality_threshold
                or not best_primary_candidate.text
                or self._looks_like_junk(best_primary_candidate)
                or self._looks_like_value_only_measurement(segment, best_primary_candidate)
                or self._looks_like_malformed_measurement_layout(segment, best_primary_candidate)
                or not primary_char_count_ok
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
                similarity = _text_similarity(best_primary_candidate.text, best_candidate.text)
                if similarity < self.disagreement_similarity_threshold:
                    disagreement_count += 1
                    fallback_disagreement = True

            needs_char_retry_policy = needs_fallback or fallback_disagreement
            fallback_trigger_reason = self._fallback_trigger_reason(
                segment,
                best_primary_candidate,
                best_primary_quality=best_primary_quality,
                primary_char_count_ok=primary_char_count_ok,
                fallback_disagreement=fallback_disagreement,
            )

            chosen = max(candidates, key=self._candidate_rank_key)
            pre_char_chosen = chosen
            pre_char_chosen_text = canonicalize_exact_line(pre_char_chosen.text)
            line_ocr_char_count = self._predicted_char_count(pre_char_chosen_text)
            line_ocr_count_matches = bool(
                expected_char_count <= 0 or line_ocr_char_count == expected_char_count
            )

            char_retry_text = ""
            char_retry_confidence = 0.0
            char_retry_min_confidence = 0.0
            char_count_predicted = self._predicted_char_count(chosen.text)
            manual_verify_required = False
            char_retry_applied = False
            can_use_char_fallback = (
                self.char_fallback_enabled
                and self.char_fallback_classifier is not None
                and needs_char_retry_policy
                and expected_char_count > 0
                and split_confidence >= self.char_fallback_min_split_confidence
            )
            if can_use_char_fallback:
                retry = self.char_fallback_classifier.predict(split_result.preprocessed_line, split_result.slices)
                char_retry_text = canonicalize_exact_line(retry.text)
                char_retry_confidence = float(retry.confidence)
                char_retry_min_confidence = float(retry.min_char_confidence)
                char_count_predicted = int(retry.predicted_count)
                retry_count_ok = char_count_predicted == expected_char_count
                retry_quality_ok = char_retry_confidence >= self.char_retry_confidence_threshold
                retry_char_conf_ok = char_retry_min_confidence >= self.char_retry_min_char_confidence
                if char_retry_text and retry_count_ok and retry_quality_ok and retry_char_conf_ok:
                    chosen = LineOcrCandidate(
                        text=char_retry_text,
                        confidence=char_retry_confidence,
                        engine_name="char-fallback",
                        view_name="vertical_slicer",
                        source="char_fallback",
                        metadata={
                            "expected_char_count": expected_char_count,
                            "predicted_char_count": char_count_predicted,
                            "split_confidence": split_confidence,
                        },
                    )
                    char_retry_applied = True
                    fallback_accept_count += 1
                else:
                    fallback_reject_count += 1
                manual_verify_required = True

            chosen_text = canonicalize_exact_line(chosen.text)
            vertical_slice_retry_attempted = False
            vertical_slice_retry_text = ""
            vertical_slice_retry_status = "first_pass_ok" if line_ocr_count_matches else "not_attempted"
            vertical_slice_retry_char_count = 0
            vertical_slice_retry_count_matches = False
            vertical_slice_mean_conf = 0.0
            vertical_slice_min_conf = 0.0
            vertical_retry_selected = False
            if (
                not line_ocr_count_matches
                and expected_char_count > 0
                and split_result.slices
            ):
                vertical_slice_retry_attempted = True
                try:
                    v_text, vertical_slice_mean_conf, vertical_slice_min_conf, _ = per_char_slice_ocr_line(
                        split_result.preprocessed_line,
                        split_result,
                        primary_engine=primary_engine,
                        fallback_engine=None,
                        preprocessor=lambda image: image,
                    )
                    vertical_slice_retry_text = canonicalize_exact_line(v_text)
                except Exception:
                    vertical_slice_retry_text = ""
                    vertical_slice_retry_status = "error"
                else:
                    vertical_slice_retry_char_count = self._predicted_char_count(vertical_slice_retry_text)
                    vertical_slice_retry_count_matches = (
                        vertical_slice_retry_char_count == expected_char_count
                    )
                    vertical_slice_retry_status = (
                        "count_match" if vertical_slice_retry_count_matches else "count_mismatch"
                    )
                    if vertical_slice_retry_count_matches and vertical_slice_retry_text.strip() and not char_retry_applied:
                        vertical_retry_candidate = LineOcrCandidate(
                            text=vertical_slice_retry_text,
                            confidence=float(vertical_slice_mean_conf),
                            engine_name=primary_engine.name,
                            view_name="vertical_slicer",
                            source="vertical_slice_retry",
                            metadata={
                                "expected_char_count": expected_char_count,
                                "predicted_char_count": vertical_slice_retry_char_count,
                                "split_confidence": split_confidence,
                            },
                        )
                        if self._candidate_quality(vertical_retry_candidate) >= max(
                            0.4, self.fallback_quality_threshold - 0.2
                        ):
                            chosen = vertical_retry_candidate
                            vertical_retry_selected = True
            elif not line_ocr_count_matches and expected_char_count > 0 and not split_result.slices:
                vertical_slice_retry_status = "no_slices"

            chosen_text = canonicalize_exact_line(chosen.text)

            if vertical_retry_selected:
                best_available_text = vertical_slice_retry_text
                best_text_source = "vertical_slice_retry"
            elif line_ocr_count_matches:
                best_available_text = pre_char_chosen_text
                best_text_source = "first_line_ocr"
            elif vertical_slice_retry_count_matches and vertical_slice_retry_text.strip():
                best_available_text = vertical_slice_retry_text
                best_text_source = "vertical_slice_retry"
            else:
                best_available_text = chosen_text
                if char_retry_applied:
                    best_text_source = "char_fallback"
                else:
                    best_text_source = "pipeline_final"

            if not chosen_text.strip():
                review_status = "error"
            elif vertical_retry_selected:
                uncertain_line = self._candidate_quality(chosen) < self.uncertain_threshold
                review_status = "review_retry_improved" if uncertain_line else "accepted"
            elif bool(manual_verify_required):
                review_status = "review_required"
            elif not line_ocr_count_matches:
                review_status = "review_required"
            else:
                uncertain_line = self._candidate_quality(chosen) < self.uncertain_threshold
                if uncertain_line:
                    review_status = "review_required"
                else:
                    review_status = "accepted"
            accept_for_training = bool(review_status == "accepted")
            needs_manual_review = bool(review_status != "accepted")

            review_note = ""
            if review_status == "review_retry_improved":
                review_note = (
                    "Line OCR character count did not match the reliable vertical slice count; "
                    "per-slice OCR count matches. Likely improved but manually verify before training."
                )
            elif review_status == "review_required" and not line_ocr_count_matches and not vertical_slice_retry_count_matches and vertical_slice_retry_attempted:
                review_note = (
                    "Line and per-slice OCR character counts still disagree with the reliable vertical slice count; "
                    "needs manual check."
                )

            retry_diagnostics = {
                "vertical_slice": {
                    "attempted": vertical_slice_retry_attempted,
                    "first_pass_char_count": line_ocr_char_count,
                    "pre_char_line_text": pre_char_chosen_text,
                    "first_pass_char_count_matches": line_ocr_count_matches,
                    "expected_char_count": expected_char_count,
                    "retry_text": vertical_slice_retry_text,
                    "retry_char_count": vertical_slice_retry_char_count,
                    "retry_char_count_matches": vertical_slice_retry_count_matches,
                    "status": vertical_slice_retry_status,
                    "mean_confidence": float(vertical_slice_mean_conf),
                    "min_confidence": float(vertical_slice_min_conf),
                    "review_note": review_note,
                    "reliable": bool(split_result.reliable),
                    "unreliable_reason": str(split_result.unreliable_reason),
                    "gap_widths": list(split_result.gap_widths),
                    "space_after": list(split_result.space_after),
                    "space_gap_threshold_px": int(split_result.space_gap_threshold_px),
                }
            }

            uncertain = self._candidate_quality(chosen) < self.uncertain_threshold or not chosen_text.strip()
            if manual_verify_required:
                manual_verify_line_count += 1
            rerank_candidates = [
                self._annotate_candidate_for_rerank(candidate, expected_char_count=expected_char_count)
                for candidate in candidates
            ]
            chosen_annotated = self._annotate_candidate_for_rerank(chosen, expected_char_count=expected_char_count)
            seen_candidate_texts = {canonicalize_exact_line(candidate.text) for candidate in rerank_candidates}
            if canonicalize_exact_line(chosen_annotated.text) not in seen_candidate_texts:
                rerank_candidates.append(chosen_annotated)
            predictions.append(
                LinePrediction(
                    order=segment.order,
                    bbox=segment.bbox,
                    text=chosen_text,
                    confidence=chosen.confidence,
                    engine_name=chosen.engine_name,
                    source=chosen.source,
                    uncertain=uncertain,
                    manual_verify_required=manual_verify_required,
                    candidates=tuple(rerank_candidates),
                    metadata={
                        "segmentation_source": segment.metadata.get("source"),
                        "token_count": segment.metadata.get("token_count", 0),
                        "candidate_count": len(candidates),
                        "candidate_quality": self._candidate_quality(chosen),
                        "best_primary_quality": best_primary_quality,
                        "fallback_trigger_reason": fallback_trigger_reason,
                        "primary_text": canonicalize_exact_line(best_primary_candidate.text),
                        "char_retry_text": char_retry_text,
                        "primary_quality": best_primary_quality,
                        "char_retry_confidence": char_retry_confidence,
                        "char_retry_min_char_confidence": char_retry_min_confidence,
                        "char_count_expected": expected_char_count,
                        "char_count_predicted": char_count_predicted,
                        "split_confidence": split_confidence,
                        "vertical_slicer_reliable": bool(split_result.reliable),
                        "vertical_slicer_unreliable_reason": str(split_result.unreliable_reason),
                        "manual_verify_required": manual_verify_required,
                        "char_retry_applied": char_retry_applied,
                        "pre_char_line_text": pre_char_chosen_text,
                        "line_ocr_char_count": line_ocr_char_count,
                        "line_ocr_count_matches": line_ocr_count_matches,
                        "vertical_slice_retry_attempted": vertical_slice_retry_attempted,
                        "vertical_slice_retry_text": vertical_slice_retry_text,
                        "vertical_slice_retry_status": vertical_slice_retry_status,
                        "vertical_slice_retry_char_count": vertical_slice_retry_char_count,
                        "vertical_slice_retry_count_matches": vertical_slice_retry_count_matches,
                        "best_available_text": best_available_text,
                        "best_text_source": best_text_source,
                        "review_status": review_status,
                        "accept_for_training": accept_for_training,
                        "needs_manual_review": needs_manual_review,
                        "retry_diagnostics": retry_diagnostics,
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
            fallback_accept_count=fallback_accept_count,
            fallback_reject_count=fallback_reject_count,
            manual_verify_line_count=manual_verify_line_count,
        )

    def _fallback_trigger_reason(
        self,
        segment: SegmentedLine,
        candidate: LineOcrCandidate,
        *,
        best_primary_quality: float,
        primary_char_count_ok: bool,
        fallback_disagreement: bool,
    ) -> str:
        if fallback_disagreement:
            return "fallback_disagreement"
        if best_primary_quality < self.fallback_quality_threshold:
            return "low_quality"
        if not candidate.text.strip():
            return "empty_text"
        if self._looks_like_junk(candidate):
            return "junk_text"
        if self._looks_like_value_only_measurement(segment, candidate):
            return "value_only"
        if self._looks_like_malformed_measurement_layout(segment, candidate):
            return "malformed_layout"
        if not primary_char_count_ok:
            return "char_count_mismatch"
        return "none"

    @staticmethod
    def _predicted_char_count(text: str) -> int:
        canonical = canonicalize_exact_line(text)
        return sum(1 for ch in canonical if not ch.isspace())

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

    def _annotate_candidate_for_rerank(
        self,
        candidate: LineOcrCandidate,
        *,
        expected_char_count: int,
    ) -> LineOcrCandidate:
        canonical = canonicalize_exact_line(candidate.text)
        observed_char_count = self._predicted_char_count(canonical)
        count_matches = bool(expected_char_count <= 0 or observed_char_count == expected_char_count)
        return LineOcrCandidate(
            text=candidate.text,
            confidence=candidate.confidence,
            engine_name=candidate.engine_name,
            view_name=candidate.view_name,
            source=candidate.source,
            tokens=candidate.tokens,
            metadata={
                **candidate.metadata,
                "char_count_expected": expected_char_count,
                "expected_char_count": expected_char_count,
                "line_ocr_char_count": observed_char_count,
                "line_ocr_count_matches": count_matches,
            },
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
        known_unit = normalize_unit(decoded.unit) if decoded.unit else None
        if decoded.unit and known_unit not in KNOWN_UNITS:
            return True
        if decoded.is_measurement:
            return False
        if self._noise_penalty(canonical) >= 0.12:
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
        if re.match(r"^[-+]?\d+(?:[.,]\d+)?\s+(?:cm|mm|ml|m/s|mmHg|%)\b", canonical, flags=re.IGNORECASE):
            return True
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
        if decoded.label and decoded.unit is None and decoded.value and re.search(r"\b(?:cm|mm|ml|m/s|mmHg|%)\b", decoded.label, flags=re.IGNORECASE):
            return True
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


def _text_similarity(lhs: str, rhs: str) -> float:
    left = _normalize_for_similarity(lhs)
    right = _normalize_for_similarity(rhs)
    if not left and not right:
        return 1.0
    return float(SequenceMatcher(a=left, b=right).ratio())
