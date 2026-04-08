from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from app.models.types import PipelineRequest
from app.pipeline.echo_ocr_pipeline import DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX, EchoOcrPipeline
from app.pipeline.measurements.line_first_parser import LineFirstParser
from app.pipeline.ocr.ocr_engines import OcrResult
from app.runtime.pipeline_presets import (
    build_gui_ocr_comparison_manager,
    build_gui_ocr_manager,
    build_validation_manager,
)


class _FakeSuryaEngine:
    name = "surya-fake"

    def extract(self, image: np.ndarray) -> OcrResult:
        _ = image
        return OcrResult(text="", confidence=1.0, tokens=[], engine_name=self.name)


class _FakeGlmEngine:
    name = "glm-ocr"

    def extract(self, image: np.ndarray) -> OcrResult:
        _ = image
        return OcrResult(text="", confidence=1.0, tokens=[], engine_name=self.name)


def test_build_validation_manager_forces_expected_configuration() -> None:
    manager = build_validation_manager(
        glm_ocr_engine=_FakeGlmEngine(),
        surya_engine=_FakeSuryaEngine(),
        llm_model="demo-model",
        llm_command="ollama",
    )
    pipeline = manager.active()

    assert isinstance(pipeline, EchoOcrPipeline)
    assert pipeline.config.parameters["ocr_engine"] == "glm-ocr"
    assert pipeline.config.parameters["scale_factor"] == 3
    assert pipeline.config.parameters["scale_algo"] == "lanczos"
    assert pipeline.config.parameters["contrast_mode"] == "none"
    assert pipeline.config.parameters["max_frames"] == 1
    assert pipeline.config.parameters["panel_validation_mode"] == "selective"
    assert pipeline.config.parameters["panel_validation_model"] == "demo-model"
    assert (
        pipeline.config.parameters["segmentation_extra_left_pad_px"]
        == DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX
    )

    pipeline._ensure_components()
    assert pipeline.ocr_engine.name == "glm-ocr"
    assert isinstance(pipeline._line_first_parser, LineFirstParser)


def test_build_gui_ocr_manager_defaults_to_glm_no_parser_adaptive_20px() -> None:
    manager = build_gui_ocr_manager(glm_ocr_engine=_FakeGlmEngine(), surya_engine=_FakeSuryaEngine())
    pipeline = manager.active()

    assert isinstance(pipeline, EchoOcrPipeline)
    assert pipeline.config.parameters["ocr_engine"] == "glm-ocr"
    assert pipeline.config.parameters["segmentation_mode"] == "adaptive"
    assert pipeline.config.parameters["target_line_height_px"] == 20.0
    assert pipeline.config.parameters["panel_validation_mode"] == "off"
    assert (
        pipeline.config.parameters["segmentation_extra_left_pad_px"]
        == DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX
    )

    pipeline._ensure_components()
    assert pipeline.ocr_engine.name == "glm-ocr"
    assert isinstance(pipeline._line_first_parser, LineFirstParser)


def test_build_gui_ocr_comparison_manager_collects_side_by_side_results() -> None:
    from app.runtime.pipeline_presets import GuiOcrComparisonPipeline

    class _StubEchoPipeline(EchoOcrPipeline):
        def __init__(self, engine_name: str) -> None:
            super().__init__()
            self.engine_name = engine_name

        def run(self, request: PipelineRequest):
            from app.models.types import AiMeasurement, AiResult, PipelineResult

            return PipelineResult(
                dicom_path=request.dicom_path,
                status="ok",
                ai_result=AiResult(
                    model_name=f"echo-ocr:{self.engine_name}",
                    created_at=datetime.now(),
                    measurements=[AiMeasurement(name=f"{self.engine_name} Vmax", value="2.1", unit="m/s")],
                    raw={
                        "exact_lines": [f"1 {self.engine_name} Vmax 2.1 m/s"],
                        "line_predictions": [{"text": f"1 {self.engine_name} Vmax 2.1 m/s"}],
                    },
                ),
                error=None,
            )

    manager = build_gui_ocr_comparison_manager(ocr_engine_names=("surya", "easyocr"))
    pipeline = manager.active()

    assert isinstance(pipeline, GuiOcrComparisonPipeline)
    pipeline._pipelines = {  # type: ignore[attr-defined]
        "surya": _StubEchoPipeline("surya"),
        "easyocr": _StubEchoPipeline("easyocr"),
    }

    result = pipeline.run(PipelineRequest(dicom_path=Path("/tmp/example.dcm")))

    assert result.status == "ok"
    assert result.ai_result is not None
    assert result.ai_result.raw["comparison_mode"] is True
    assert result.ai_result.raw["selected_ocr_engines"] == ["surya", "easyocr"]
    comparison = result.ai_result.raw["engine_comparison"]
    assert isinstance(comparison, list)
    assert comparison[0]["engine"] == "surya"
    assert comparison[1]["engine"] == "easyocr"
    assert pipeline.config.parameters["comparison_mode"] is True


def test_gui_comparison_manager_rejects_unknown_engine() -> None:
    try:
        _ = build_gui_ocr_comparison_manager(ocr_engine_names=("surya", "unknown"))
    except ValueError as exc:
        assert "Unsupported OCR engine" in str(exc)
    else:
        raise AssertionError("Expected unsupported OCR engine to raise ValueError")
