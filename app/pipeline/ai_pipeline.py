from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.models.types import AiMeasurement, AiResult, OverlayBox, PipelineRequest, PipelineResult


class AiPipelineError(RuntimeError):
    pass


class AiPipeline(Protocol):
    name: str

    def run(self, request: PipelineRequest) -> PipelineResult: ...


@dataclass
class PipelineConfig:
    enabled: bool = True
    output_dir: Path | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def with_parameters(cls, parameters: dict[str, Any]) -> PipelineConfig:
        cfg = cls()
        cfg.parameters = dict(parameters)
        return cfg


class BasePipeline:
    name = "base-pipeline"

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def run(self, request: PipelineRequest) -> PipelineResult:
        raise NotImplementedError("Pipeline must implement run().")

    def _resolve_output_dir(self, request: PipelineRequest) -> Path | None:
        if request.output_dir is not None:
            return request.output_dir
        return self.config.output_dir


class NoopPipeline(BasePipeline):
    name = "noop"

    def run(self, request: PipelineRequest) -> PipelineResult:
        return PipelineResult(
            dicom_path=request.dicom_path,
            status="skipped",
            ai_result=None,
            error=None,
        )


class DummyEchoPipeline(BasePipeline):
    """
    Placeholder pipeline that returns fake results.
    Useful for wiring UI and export flows before real AI is plugged in.
    """

    name = "dummy-echo"

    def run(self, request: PipelineRequest) -> PipelineResult:
        now = datetime.now(timezone.utc)
        ai_result = AiResult(
            model_name=self.name,
            created_at=now,
            boxes=[
                OverlayBox(x=0.05, y=0.05, width=0.2, height=0.2, label="demo", confidence=0.42),
            ],
            measurements=[
                AiMeasurement(name="Example", value="123", unit="ms", source="demo"),
            ],
            raw={
                "note": "This is a placeholder result. Replace with real model output.",
                "path": str(request.dicom_path),
            },
        )
        return PipelineResult(
            dicom_path=request.dicom_path,
            status="ok",
            ai_result=ai_result,
            error=None,
        )


class PipelineManager:
    """
    Central registry for pipelines. Keeps the app extensible:
    add new pipelines, switch active pipeline, and run.
    """

    def __init__(self) -> None:
        self._pipelines: dict[str, AiPipeline] = {}
        self._active_name: str | None = None

    def register(self, pipeline: AiPipeline) -> None:
        self._pipelines[pipeline.name] = pipeline
        if self._active_name is None:
            self._active_name = pipeline.name

    def unregister(self, name: str) -> None:
        if name in self._pipelines:
            del self._pipelines[name]
        if self._active_name == name:
            self._active_name = next(iter(self._pipelines), None)

    def list(self) -> Sequence[str]:
        return sorted(self._pipelines.keys())

    def set_active(self, name: str) -> None:
        if name not in self._pipelines:
            raise AiPipelineError(f"Pipeline not found: {name}")
        self._active_name = name

    def active(self) -> AiPipeline | None:
        if self._active_name is None:
            return None
        return self._pipelines.get(self._active_name)

    def run(self, request: PipelineRequest) -> PipelineResult:
        pipeline = self.active()
        if pipeline is None:
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="error",
                ai_result=None,
                error="No pipeline registered.",
            )
        return pipeline.run(request)


def build_default_manager(config: PipelineConfig | None = None) -> PipelineManager:
    from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline

    manager = PipelineManager()
    manager.register(NoopPipeline(config=config))
    manager.register(DummyEchoPipeline(config=config))
    try:
        manager.register(EchoOcrPipeline(config=config))
    except Exception:
        # Optional OCR dependencies can be missing in some environments.
        pass
    manager.set_active("dummy-echo")
    return manager
