from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline

__all__ = ["EchoOcrPipeline"]


def __getattr__(name: str) -> object:
    if name != "EchoOcrPipeline":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline

    return EchoOcrPipeline
