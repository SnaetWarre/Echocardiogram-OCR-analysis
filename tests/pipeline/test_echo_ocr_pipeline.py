from __future__ import annotations

from pathlib import Path

import numpy as np

from app.models.types import AiMeasurement
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import (
    EchoOcrPipeline,
    RegexMeasurementParser,
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
    preprocess_roi,
)
from app.pipeline.ocr_engines import OcrResult, OcrToken


def test_detector_finds_top_left_box() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[8:30, 10:90, 0] = 95
    frame[8:30, 10:90, 1] = 115
    frame[8:30, 10:90, 2] = 135

    detection = TopLeftBlueGrayBoxDetector(min_pixels=100).detect(frame)

    assert detection.present is True
    assert detection.bbox is not None
    x, y, width, height = detection.bbox
    assert x <= 12
    assert y <= 10
    assert width >= 70
    assert height >= 18


def test_parser_extracts_value_and_unit() -> None:
    parser = RegexMeasurementParser()
    items = parser.parse("PV Vmax 0.87 m/s\nPV maxPG 3 mmHg", confidence=0.9)

    assert len(items) == 2
    assert items[0].name == "PV Vmax"
    assert items[0].value == "0.87"
    assert items[0].unit == "m/s"


def test_preprocess_roi_respects_upscale_env(monkeypatch) -> None:
    roi = np.zeros((8, 12, 3), dtype=np.uint8)
    roi[:, :, 0] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 20
    roi[:, :, 1] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 40
    roi[:, :, 2] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 60
    monkeypatch.setenv("ECHO_OCR_UPSCALE_FACTOR", "3")
    monkeypatch.setenv("ECHO_OCR_UPSCALE_INTERPOLATION", "nearest")

    processed = preprocess_roi(roi)

    assert processed.shape == (24, 36)


class _FakeOcrEngine:
    def __init__(self, text: str, *, name: str = "fake-ocr", confidence: float = 0.95) -> None:
        self._text = text
        self.name = name
        self._confidence = confidence

    def extract(self, image: np.ndarray) -> OcrResult:
        return OcrResult(
            text=self._text,
            confidence=self._confidence,
            tokens=[OcrToken(text=self._text, confidence=self._confidence)],
            engine_name=self.name,
        )


class _FixedParser:
    def __init__(self, items: list[AiMeasurement]) -> None:
        self._items = items

    def parse(self, text: str, *, confidence: float) -> list[AiMeasurement]:
        return list(self._items)


def test_extract_measurements_uses_detector_bbox_only() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    parser = _FixedParser([AiMeasurement(name="TR Vmax", value="2.1", unit="m/s", source="test")])
    pipeline = EchoOcrPipeline(ocr_engine=_FakeOcrEngine("TR Vmax 2.1 m/s"), parser=parser)
    pipeline._ensure_components()

    ocr, items, bbox = pipeline._extract_measurements_for_frame(
        frame,
        RoiDetection(present=True, bbox=(0, 0, 64, 24), confidence=1.0),
    )

    assert ocr is not None
    assert bbox == (0, 0, 64, 24)
    assert len(items) == 1
    assert items[0].name == "TR Vmax"


def test_extract_records_persists_single_engine_metadata() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[:24, :64, 0] = 0x1A
    frame[:24, :64, 1] = 0x21
    frame[:24, :64, 2] = 0x29
    pipeline = EchoOcrPipeline(
        ocr_engine=_FakeOcrEngine("TR Vmax 2.1 m/s", name="engine-a", confidence=0.9),
        parser=RegexMeasurementParser(),
        config=PipelineConfig(),
    )
    pipeline._ensure_components()

    class _SeriesMetadata:
        study_instance_uid = "study"
        series_instance_uid = "series"
        sop_instance_uid = "sop"

    class _Series:
        metadata = _SeriesMetadata()
        frame_count = 1

        def get_frame(self, index: int) -> np.ndarray:
            return frame

    records = list(pipeline._extract_records(_Series(), Path("example.dcm")))

    assert records
    assert records[0].ocr_engine == "engine-a"
