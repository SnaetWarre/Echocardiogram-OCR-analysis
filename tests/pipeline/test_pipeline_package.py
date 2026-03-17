from __future__ import annotations

import importlib


def test_pipeline_package_exports_echo_pipeline_lazily() -> None:
    module = importlib.import_module("app.pipeline")

    assert module.__all__ == ["EchoOcrPipeline"]
    assert "EchoOcrPipeline" not in module.__dict__
