from __future__ import annotations

from app.pipeline.ai_pipeline import PipelineConfig, PipelineManager
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.measurement_parsers import LocalLlmMeasurementParser, LocalLlmParserConfig
from app.pipeline.ocr_engines import OcrEngine, build_engine


def build_validation_manager(
    *,
    surya_engine: OcrEngine | None = None,
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M",
    llm_command: str = "ollama",
) -> PipelineManager:
    engine = surya_engine if surya_engine is not None else build_engine("surya")
    parser = LocalLlmMeasurementParser(
        config=LocalLlmParserConfig(
            model=llm_model,
            command=llm_command,
            timeout_s=30.0,
        )
    )
    pipeline = EchoOcrPipeline(
        ocr_engine=engine,
        parser=parser,
        config=PipelineConfig(
            parameters={
                "ocr_engine": "surya",
                "parser_mode": "local_llm",
                "scale_factor": 3,
                "scale_algo": "lanczos",
                "contrast_mode": "none",
                "max_frames": 1,
            }
        ),
    )

    manager = PipelineManager()
    manager.register(pipeline)
    manager.set_active(pipeline.name)
    return manager
