from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.layout.line_segmenter import SegmentationResult, SegmentedLine
from app.pipeline.ocr.char_fallback import CharFallbackPrediction
from app.pipeline.transcription.line_transcriber import LineTranscriber
from app.pipeline.ocr.ocr_engines import OcrResult, OcrToken


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


class _CharFallbackStub:
    def __init__(self, prediction: CharFallbackPrediction) -> None:
        self.prediction = prediction
        self.calls = 0

    def predict(self, line_image: np.ndarray, slices: tuple[object, ...]) -> CharFallbackPrediction:
        _ = line_image
        _ = slices
        self.calls += 1
        return self.prediction


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
    fallback = _SequenceEngine([("better first", 0.88), ("good second", 0.91)], name="fallback")

    result = LineTranscriber(uncertain_threshold=0.7).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 2
    assert [line.text for line in result.lines] == ["better first", "good second"]
    assert result.engine_disagreement_count == 2


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


def test_line_transcriber_does_not_trigger_fallback_for_harmless_multiview_disagreement() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("LVOT Diam 2.0 cm", 0.95), ("LVOT Diam 2.0~cm", 0.95)], name="primary")
    fallback = _RecordingEngine([("fallback text", 0.8)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert primary.calls == 2
    assert fallback.calls == 0
    assert result.fallback_invocations == 0


def test_line_transcriber_triggers_fallback_for_junky_primary_candidate() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("0.09 m/s", 0.99), ("0.09 m/s ->", 0.99)], name="primary")
    fallback = _RecordingEngine([("1 E' Lat 0.09 m/s", 0.8), ("1 E' Lat 0.09 m/s", 0.82)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert primary.calls == 2
    assert fallback.calls >= 1
    assert result.fallback_invocations == 1
    assert result.lines[0].text == "1 E' Lat 0.09 m/s"


def test_line_transcriber_keeps_repaired_primary_candidate_without_fallback() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("L¥IDd 5.0 em", 0.95), ("LVIDd 5.0 cm", 0.94)], name="primary")
    fallback = _RecordingEngine([("fallback text", 0.8)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert fallback.calls == 0
    assert result.lines[0].text == "LVIDd 5.0 cm"


def test_line_transcriber_triggers_fallback_for_malformed_sparse_measurement_layout() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("Ao Diam\ncm\n5.1", 0.99), ("nonsense", 0.99)], name="primary")
    fallback = _RecordingEngine([("1 Ao Diam 3.1 cm", 0.84), ("1 Ao Diam 3.1 cm", 0.82)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 1
    assert result.lines[0].text == "1 Ao Diam 3.1 cm"


def test_line_transcriber_triggers_fallback_for_value_unit_first_sparse_junk() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("0.06 m/s £27", 0.99), ("noise", 0.99)], name="primary")
    fallback = _RecordingEngine([("1 E' Lat 0.06 m/s", 0.81), ("1 E' Lat 0.06 m/s", 0.78)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 1
    assert result.lines[0].text == "1 E' Lat 0.06 m/s"


def test_line_transcriber_triggers_fallback_for_unknown_unit_sparse_junk() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("Dam יגש cm /4 !", 0.99), ("noise", 0.99)], name="primary")
    fallback = _RecordingEngine([("1 LA Diam 4.0 cm", 0.78), ("1 LA Diam 4.0 cm", 0.76)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 1
    assert result.lines[0].text == "1 LA Diam 4.0 cm"


def test_line_transcriber_accepts_char_fallback_when_guardrails_pass() -> None:
    roi = np.ones((24, 72), dtype=np.uint8) * 255
    cv2.putText(roi, "123456", (2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_AA)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 48, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 72, 24), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("bad", 0.1)], name="primary")
    fallback = _RecordingEngine([("still bad", 0.1)], name="fallback")
    char_stub = _CharFallbackStub(
        CharFallbackPrediction(
            text="12.5cm",
            confidence=0.9,
            per_char_confidence=(0.9, 0.9, 0.9, 0.9, 0.9, 0.9),
            predicted_count=6,
        )
    )

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        char_fallback_enabled=True,
        char_fallback_classifier=char_stub,
        char_fallback_min_split_confidence=0.0,
        char_retry_confidence_threshold=0.2,
        preprocess_views={"default": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert char_stub.calls == 1
    assert result.fallback_accept_count == 1
    assert result.lines[0].source == "char_fallback"
    assert result.lines[0].manual_verify_required is True


def test_line_transcriber_rejects_char_fallback_when_guardrails_fail() -> None:
    roi = np.ones((24, 72), dtype=np.uint8) * 255
    cv2.putText(roi, "123456", (2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_AA)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 48, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 72, 24), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("bad", 0.1)], name="primary")
    fallback = _RecordingEngine([("still bad", 0.1)], name="fallback")
    char_stub = _CharFallbackStub(
        CharFallbackPrediction(
            text="999",
            confidence=0.1,
            per_char_confidence=(0.1, 0.1, 0.1),
            predicted_count=3,
        )
    )

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        char_fallback_enabled=True,
        char_fallback_classifier=char_stub,
        char_fallback_min_split_confidence=0.0,
        char_retry_confidence_threshold=0.95,
        preprocess_views={"default": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert char_stub.calls == 1
    assert result.fallback_reject_count == 1
    assert result.lines[0].source != "char_fallback"
    assert result.lines[0].manual_verify_required is True


def test_line_transcriber_rejects_char_retry_on_low_min_char_confidence() -> None:
    roi = np.ones((24, 72), dtype=np.uint8) * 255
    cv2.putText(roi, "123456", (2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_AA)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 48, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 72, 24), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("bad", 0.1)], name="primary")
    fallback = _RecordingEngine([("still bad", 0.1)], name="fallback")
    char_stub = _CharFallbackStub(
        CharFallbackPrediction(
            text="12.5cm",
            confidence=0.95,
            per_char_confidence=(0.95, 0.9, 0.2, 0.93, 0.96, 0.94),
            predicted_count=6,
        )
    )

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        char_fallback_enabled=True,
        char_fallback_classifier=char_stub,
        char_fallback_min_split_confidence=0.0,
        char_retry_confidence_threshold=0.5,
        char_retry_min_char_confidence=0.4,
        preprocess_views={"default": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert char_stub.calls == 1
    assert result.fallback_reject_count == 1
    assert result.lines[0].source != "char_fallback"


def test_line_transcriber_marks_fallback_disagreement_trigger_reason() -> None:
    roi = np.zeros((20, 40), dtype=np.uint8)
    segmentation = SegmentationResult(
        header_trim_px=0,
        content_bbox=(0, 0, 40, 20),
        lines=(
            SegmentedLine(order=0, bbox=(0, 0, 40, 20), metadata={"token_count": 1}),
        ),
    )
    primary = _RecordingEngine([("bad sparse", 0.3), ("bad sparse", 0.3)], name="primary")
    fallback = _RecordingEngine([("1 E' Lat 0.09 m/s", 0.85), ("1 E' Lat 0.09 m/s", 0.85)], name="fallback")

    result = LineTranscriber(
        uncertain_threshold=0.7,
        fallback_quality_threshold=0.72,
        preprocess_views={"default": lambda image: image, "clahe": lambda image: image},
    ).transcribe(
        roi,
        segmentation,
        primary_engine=primary,
        fallback_engine=fallback,
    )

    assert result.fallback_invocations == 1
    assert result.lines[0].metadata["fallback_trigger_reason"] == "fallback_disagreement"
