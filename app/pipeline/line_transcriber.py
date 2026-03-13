from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.pipeline.line_segmenter import SegmentationResult, SegmentedLine
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
        preprocess_views: dict[str, Callable[[np.ndarray], np.ndarray]] | None = None,
    ) -> None:
        self.uncertain_threshold = float(uncertain_threshold)
        self.disagreement_similarity_threshold = float(disagreement_similarity_threshold)
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
        fallback_views = view_items[1:]

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

            needs_fallback = primary_candidate.confidence < self.uncertain_threshold or not primary_candidate.text
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

                for view_name, preprocessor in fallback_views:
                    fallback_view_result = fallback_engine.extract(preprocessor(raw_crop))
                    candidates.append(
                        _candidate_from_result(
                            result=fallback_view_result,
                            source="fallback_multiview",
                            view_name=view_name,
                            metadata={"segment_order": segment.order, "view": view_name},
                        )
                    )

            chosen = max(
                candidates,
                key=lambda item: (item.confidence, len(item.text.strip()), item.engine_name == primary_engine.name),
            )
            uncertain = chosen.confidence < self.uncertain_threshold or not chosen.text.strip()
            predictions.append(
                LinePrediction(
                    order=segment.order,
                    bbox=segment.bbox,
                    text=chosen.text,
                    confidence=chosen.confidence,
                    engine_name=chosen.engine_name,
                    source=chosen.source,
                    uncertain=uncertain,
                    candidates=tuple(candidates),
                    metadata={
                        "segmentation_source": segment.metadata.get("source"),
                        "token_count": segment.metadata.get("token_count", 0),
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


def _normalize_for_similarity(text: str) -> str:
    return " ".join(text.lower().split())
