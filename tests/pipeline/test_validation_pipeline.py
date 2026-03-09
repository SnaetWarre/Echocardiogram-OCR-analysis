from __future__ import annotations

import numpy as np

from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.ocr_engines import OcrResult
from app.pipeline.validation_pipeline import build_validation_manager


class _FakeSuryaEngine:
    name = "surya-fake"

    def extract(self, image: np.ndarray) -> OcrResult:
        _ = image
        return OcrResult(text="", confidence=1.0, tokens=[], engine_name=self.name)


def test_build_validation_manager_forces_expected_configuration() -> None:
    manager = build_validation_manager(
        surya_engine=_FakeSuryaEngine(),
        llm_model="demo-model",
        llm_command="ollama",
    )
    pipeline = manager.active()

    assert isinstance(pipeline, EchoOcrPipeline)
    assert pipeline.config.parameters["ocr_engine"] == "surya"
    assert pipeline.config.parameters["parser_mode"] == "local_llm"
    assert pipeline.config.parameters["scale_factor"] == 3
    assert pipeline.config.parameters["scale_algo"] == "lanczos"
    assert pipeline.config.parameters["contrast_mode"] == "none"
    assert pipeline.config.parameters["max_frames"] == 1

    pipeline._ensure_components()
    assert pipeline.ocr_engine.name == "surya-fake"
    assert pipeline.parser.__class__.__name__ == "LocalLlmMeasurementParser"
