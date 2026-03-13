from __future__ import annotations

import numpy as np

from app.pipeline.line_segmenter import SegmentationResult, SegmentedLine
from app.pipeline.line_transcriber import LineTranscriber
from app.pipeline.ocr_engines import OcrResult, OcrToken


class _SequenceEngine:
    def __init__(self, outputs: list[tuple[str, float]], *, name: str) -> None:
        self._outputs = list(outputs)
        self.name = name

    def extract(self, image: np.ndarray) -> OcrResult:
        _ = image
        text, confidence = self._outputs.pop(0)
        return OcrResult(
            text=text,
            confidence=confidence,
            tokens=[OcrToken(text=text, confidence=confidence)],
            engine_name=self.name,
        )


class _RecordingEngine:
    def __init__(self, outputs: list[tuple[str, float]], *, name: str) -> None:
        self._outputs = list(outputs)
        self.name = name
        self.calls = 0

    def extract(self, image: np.ndarray) -> OcrResult:
        _ = image
        self.calls += 1
        text, confidence = self._outputs[min(self.calls - 1, len(self._outputs) - 1)]
        return OcrResult(
            text=text,
            confidence=confidence,
            tokens=[OcrToken(text=text, confidence=confidence)],
            engine_name=self.name,
        )


def test_line_transcriber_routes_uncertain_lines_to_fallback_engine() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 10)),
            SegmentedLine(order=1, bbox=(0, 10, 40, 10)),
        ),
    )
    primary = _SequenceEngine([("bad", 0.3), ("good second", 0.92)], name="primary")
    fallback = _SequenceEngine([("better first", 0.88)], name="fallback")

    result = LineTranscriber(uncertain_threshold=0.7).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 1
    assert [line.text for line in result.lines] == ["better first", "good second"]
    assert result.engine_disagreement_count == 1


def test_line_transcriber_tries_primary_multiview_for_sparse_single_token_segments() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("bad sparse", 0.7), ("better sparse", 0.92)], name="primary")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=None,
    )

    assert primary.calls == 2
    assert result.lines[0].text == "better sparse"
    assert result.lines[0].metadata["candidate_count"] == 2
