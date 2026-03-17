from __future__ import annotations

from pathlib import Path

import numpy as np

from app.models.types import AiMeasurement
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import (
    DEFAULT_FALLBACK_OCR_ENGINE,
    DEFAULT_OCR_ENGINE,
    DEFAULT_PARSER_MODE,
    DEFAULT_SEGMENTATION_MODE,
    DEFAULT_TARGET_LINE_HEIGHT_PX,
    EchoOcrPipeline,
    RegexMeasurementParser,
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
    preprocess_roi,
)
from app.pipeline.line_transcriber import LinePrediction, PanelTranscription
from app.pipeline.panel_validator import LocalLlmPanelValidator, PanelValidatorConfig
from app.pipeline.ocr_engines import OcrResult, OcrToken


def test_detector_finds_measurement_roi_from_strict_color_mask() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[:, :, 0] = 200
    frame[:, :, 1] = 200
    frame[:, :, 2] = 200

    frame[8:30, 10:90, 0] = 0x1A
    frame[8:30, 10:90, 1] = 0x21
    frame[8:30, 10:90, 2] = 0x29

    detection = TopLeftBlueGrayBoxDetector(min_pixels=100).detect(frame)

    assert detection.present is True
    assert detection.bbox is not None
    x, y, width, height = detection.bbox
    assert 8 <= x <= 12
    assert 8 <= y <= 10
    assert 78 <= width <= 82
    assert 20 <= height <= 24


def test_detector_uses_target_color_connected_component_roi() -> None:
    frame = np.zeros((140, 220, 3), dtype=np.uint8)
    frame[:, :, 0] = 200
    frame[:, :, 1] = 200
    frame[:, :, 2] = 200

    frame[8:30, 10:90, 0] = 0x1A
    frame[8:30, 10:90, 1] = 0x21
    frame[8:30, 10:90, 2] = 0x29

    frame[12:26, 24:76, 0] = 255
    frame[12:26, 24:76, 1] = 255
    frame[12:26, 24:76, 2] = 255

    frame[60:95, 120:180, 0] = 0x1A
    frame[60:95, 120:180, 1] = 0x21
    frame[60:95, 120:180, 2] = 0x29

    detection = TopLeftBlueGrayBoxDetector(min_pixels=100).detect(frame)

    assert detection.present is True
    assert detection.bbox is not None
    x, y, width, height = detection.bbox
    assert 8 <= x <= 12
    assert 8 <= y <= 10
    assert 78 <= width <= 82
    assert 20 <= height <= 24


def test_parser_extracts_value_and_unit() -> None:
    parser = RegexMeasurementParser()
    items = parser.parse("PV Vmax 0.87 m/s\nPV maxPG 3 mmHg", confidence=0.9)

    assert len(items) == 2
    assert items[0].name == "PV Vmax"
    assert items[0].value == "0.87"
    assert items[0].unit == "m/s"


def test_parser_preserves_compound_unit_without_truncation() -> None:
    parser = RegexMeasurementParser()
    items = parser.parse("Ao Desc Diam 2.0 cm2", confidence=0.9)

    assert len(items) == 1
    assert items[0].name == "Ao Desc Diam"
    assert items[0].value == "2.0"
    assert items[0].unit == "cm2"


def test_preprocess_roi_respects_upscale_env(monkeypatch) -> None:
    roi = np.zeros((8, 12, 3), dtype=np.uint8)
    roi[:, :, 0] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 20
    roi[:, :, 1] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 40
    roi[:, :, 2] = np.tile(np.arange(12, dtype=np.uint8), (8, 1)) + 60
    monkeypatch.setenv("ECHO_OCR_UPSCALE_FACTOR", "3")
    monkeypatch.setenv("ECHO_OCR_UPSCALE_INTERPOLATION", "nearest")

    processed = preprocess_roi(roi)

    assert processed.shape == (24, 36)


def test_extract_measurements_trims_14px_header_before_ocr() -> None:
    frame = np.zeros((80, 160, 3), dtype=np.uint8)
    parser = _FixedParser([AiMeasurement(name="PV Vmax", value="0.96", unit="m/s", source="test")])
    pipeline = EchoOcrPipeline(ocr_engine=_FakeOcrEngine("PV Vmax 0.96 m/s"), parser=parser)
    pipeline._ensure_components()

    captured_shapes: list[tuple[int, int, int]] = []

    class _CapturingEngine(_FakeOcrEngine):
        def extract(self, image: np.ndarray) -> OcrResult:
            captured_shapes.append(image.shape)
            return super().extract(image)

    pipeline.ocr_engine = _CapturingEngine("PV Vmax 0.96 m/s")

    ocr, panel, items, bbox = pipeline._extract_measurements_for_frame(
        frame,
        RoiDetection(present=True, bbox=(0, 0, 64, 24), confidence=1.0),
    )

    assert ocr is not None
    assert panel.lines
    assert bbox == (0, 0, 64, 24)
    assert len(items) == 1
    assert captured_shapes
    assert captured_shapes[0][0] <= 72


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

    ocr, panel, items, bbox = pipeline._extract_measurements_for_frame(
        frame,
        RoiDetection(present=True, bbox=(0, 0, 64, 24), confidence=1.0),
    )

    assert ocr is not None
    assert panel.lines
    assert bbox == (0, 0, 64, 24)
    assert len(items) == 1
    assert items[0].name == "1 TR Vmax"


def test_extract_records_persists_single_engine_metadata() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[:, :, 0] = 200
    frame[:, :, 1] = 200
    frame[:, :, 2] = 200
    frame[5:29, 0:64, 0] = 0x1A
    frame[5:29, 0:64, 1] = 0x21
    frame[5:29, 0:64, 2] = 0x29
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
    assert records[0].exact_line_text
    assert records[0].line_bbox is not None


def test_extract_records_respects_max_frames_limit() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[:, :, 0] = 200
    frame[:, :, 1] = 200
    frame[:, :, 2] = 200
    frame[5:29, 0:64, 0] = 0x1A
    frame[5:29, 0:64, 1] = 0x21
    frame[5:29, 0:64, 2] = 0x29

    parser = _FixedParser([AiMeasurement(name="TR Vmax", value="2.1", unit="m/s", source="test")])
    pipeline = EchoOcrPipeline(
        ocr_engine=_FakeOcrEngine("TR Vmax 2.1 m/s", name="engine-a", confidence=0.9),
        parser=parser,
        config=PipelineConfig(parameters={"max_frames": 1}),
    )
    pipeline._ensure_components()

    class _SeriesMetadata:
        study_instance_uid = "study"
        series_instance_uid = "series"
        sop_instance_uid = "sop"

    class _Series:
        metadata = _SeriesMetadata()
        frame_count = 3

        def get_frame(self, index: int) -> np.ndarray:
            _ = index
            return frame

    records = list(pipeline._extract_records(_Series(), Path("example.dcm"), max_frames=1))

    assert len(records) == 1
    assert records[0].frame_index == 0


def test_ai_result_uses_exact_line_sources_and_raw_line_predictions() -> None:
    pipeline = EchoOcrPipeline()
    records = [
        pipeline._extract_records  # keep pyright from complaining about instantiation context
    ]
    _ = records

    from app.pipeline.echo_ocr_schema import MeasurementRecord

    result = pipeline._to_ai_result(
        [
            MeasurementRecord(
                study_uid="study",
                series_uid="series",
                sop_instance_uid="sop",
                frame_index=0,
                measurement_name="TR Vmax",
                measurement_value="2.1",
                measurement_unit="m/s",
                exact_line_text="1 TR Vmax 2.1 m/s",
                line_confidence=0.88,
                line_uncertain=False,
                ocr_text_raw="1 TR Vmax 2.1 m/s",
                ocr_confidence=0.88,
                parser_confidence=0.88,
                roi_bbox=(0, 0, 10, 10),
                line_bbox=(0, 0, 10, 2),
                text_order=0,
                processed_at="now",
                pipeline_version="v2-line-first",
                ocr_engine="fake-ocr",
            )
        ]
    )

    assert result.measurements[0].source == "exact_line:1 TR Vmax 2.1 m/s:0.880"
    assert result.raw["exact_lines"] == ["1 TR Vmax 2.1 m/s"]
    assert result.raw["line_predictions"][0]["line_bbox"] == [0, 0, 10, 2]
    assert result.raw["segmentation_mode"] == "fixed_pitch"
    assert result.raw["target_line_height_px"] == 20.0


def test_pipeline_respects_fixed_pitch_segmentation_parameters() -> None:
    pipeline = EchoOcrPipeline(
        config=PipelineConfig(
            parameters={
                "segmentation_mode": "fixed_pitch",
                "target_line_height_px": 20.0,
            }
        )
    )

    assert pipeline._line_segmenter.segmentation_mode == "fixed_pitch"
    assert pipeline._line_segmenter.target_line_height_px == 20.0


def test_pipeline_supports_strict_engine_selection_flag() -> None:
    pipeline = EchoOcrPipeline(
        config=PipelineConfig(
            parameters={
                "strict_ocr_engine_selection": True,
            }
        )
    )

    assert pipeline._strict_ocr_engine_selection is True


def test_pipeline_defaults_match_line_first_validation_configuration() -> None:
    pipeline = EchoOcrPipeline()

    assert pipeline._default_engine == DEFAULT_OCR_ENGINE
    assert pipeline._fallback_engine_name == DEFAULT_FALLBACK_OCR_ENGINE
    assert pipeline._parser_mode == DEFAULT_PARSER_MODE
    assert pipeline._segmentation_mode == DEFAULT_SEGMENTATION_MODE
    assert pipeline._target_line_height_px == DEFAULT_TARGET_LINE_HEIGHT_PX


def test_panel_validator_results_are_reattached_to_exact_lines() -> None:
    pipeline = EchoOcrPipeline()
    pipeline._panel_validator = LocalLlmPanelValidator(
        config=PanelValidatorConfig(mode="always"),
        runner=lambda _prompt: '{"measurements":[{"order":1,"name":"TR Vmax","value":"2.1","unit":"m/s"}]}',
    )
    panel = PanelTranscription(
        lines=(
            LinePrediction(
                order=0,
                bbox=(0, 0, 20, 4),
                text="TR Vmax 2.1 m/s",
                confidence=0.82,
                engine_name="fake",
                source="primary",
                uncertain=True,
            ),
        ),
        combined_text="TR Vmax 2.1 m/s",
        uncertain_line_count=1,
    )

    refined = pipeline._maybe_apply_panel_validator(
        panel,
        [AiMeasurement(name="TR Vmax", value="2.1", unit="ms", order_hint=0)],
        confidence=0.8,
    )

    assert refined[0].unit == "m/s"
    assert refined[0].source is not None
    assert "|parser=panel_validator:" in refined[0].source
