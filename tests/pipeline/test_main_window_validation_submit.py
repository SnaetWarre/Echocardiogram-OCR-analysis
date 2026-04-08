from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DICOM_AI_ENABLED", "0")

from PySide6 import QtWidgets

from app.models.types import AiMeasurement, AiResult, OverlayBox
from app.pipeline.ai_pipeline import PipelineManager
from app.runtime.pipeline_presets import GuiOcrComparisonPipeline
from app.ui.main_window import MainWindow


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_validation_submit_skips_output_when_false_positive(tmp_path: Path) -> None:
    _ = _get_app()
    window = MainWindow()
    output_path = tmp_path / "exact_lines.json"
    window._validation_writer._output_path = output_path
    original_information = QtWidgets.QMessageBox.information
    QtWidgets.QMessageBox.information = lambda *args, **kwargs: 0  # type: ignore[assignment]

    try:
        window._on_validation_submitted(
            Path("/tmp/example.dcm"),
            ["TR Vmax 1.9 m/s"],
            0,
            1,
            True,
        )
    finally:
        QtWidgets.QMessageBox.information = original_information  # type: ignore[assignment]

    assert not output_path.exists()
    assert window._state.validation_session.total_validated_frames == 1
    assert window._state.validation_session.total_ai_incorrect == 1


def test_validation_submit_writes_labels_json(tmp_path: Path) -> None:
    _ = _get_app()
    window = MainWindow()
    output_path = tmp_path / "exact_lines.json"
    window._validation_writer._output_path = output_path
    original_information = QtWidgets.QMessageBox.information
    QtWidgets.QMessageBox.information = lambda *args, **kwargs: 0  # type: ignore[assignment]

    try:
        window._on_validation_submitted(
            Path("/tmp/example.dcm"),
            ["TR Vmax 1.9 m/s", "TR maxPG 14 mmHg"],
            2,
            0,
            False,
        )
    finally:
        QtWidgets.QMessageBox.information = original_information  # type: ignore[assignment]

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["files"] == [
        {
            "file_name": "example.dcm",
            "file_path": "/tmp/example.dcm",
            "split": "validation",
            "measurements": [
                {"order": 1, "text": "TR Vmax 1.9 m/s"},
                {"order": 2, "text": "TR maxPG 14 mmHg"},
            ],
        }
    ]
    assert window._state.validation_session.total_validated_frames == 1
    assert window._state.validation_session.total_ai_correct == 2


def test_ensure_validation_manager_uses_selected_single_engine(monkeypatch) -> None:
    from app.pipeline.ai_pipeline import PipelineConfig, PipelineManager
    from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
    from app.pipeline.ocr.ocr_engines import OcrResult

    def _fake_build_gui_ocr_manager(
        *,
        ocr_engine_name: str = "glm-ocr",
        glm_ocr_engine=None,
        surya_engine=None,
        **kwargs: object,
    ) -> PipelineManager:
        _ = glm_ocr_engine, surya_engine, kwargs

        class _StubEngine:
            name = ocr_engine_name

            def extract(self, image: object) -> OcrResult:
                _ = image
                return OcrResult(text="", confidence=1.0, tokens=[], engine_name=self.name)

        pipeline = EchoOcrPipeline(
            ocr_engine=_StubEngine(),
            config=PipelineConfig(
                parameters={
                    "ocr_engine": ocr_engine_name,
                    "target_line_height_px": 20.0,
                }
            ),
        )
        mgr = PipelineManager()
        mgr.register(pipeline)
        mgr.set_active(pipeline.name)
        return mgr

    monkeypatch.setattr("app.ui.main_window.build_gui_ocr_manager", _fake_build_gui_ocr_manager)

    _ = _get_app()
    window = MainWindow()
    window._set_selected_ocr_engines(("easyocr",))

    manager = window._ensure_validation_manager()
    pipeline = manager.active()

    assert manager is window._state.pipeline_manager
    assert pipeline is not None
    assert getattr(getattr(pipeline, "config", None), "parameters", {}).get("ocr_engine") == "easyocr"
    assert getattr(getattr(pipeline, "config", None), "parameters", {}).get("target_line_height_px") == 20.0


def test_ensure_validation_manager_uses_comparison_pipeline_for_multi_select() -> None:
    _ = _get_app()
    window = MainWindow()
    window._set_selected_ocr_engines(("surya", "easyocr"))

    manager = window._ensure_validation_manager()
    pipeline = manager.active()

    assert isinstance(manager, PipelineManager)
    assert isinstance(pipeline, GuiOcrComparisonPipeline)


def test_build_viewer_overlay_boxes_adds_line_debug_boxes_when_enabled() -> None:
    _ = _get_app()
    window = MainWindow()
    window._overlay_mode = "detailed"
    result = AiResult(
        model_name="demo",
        created_at=__import__("datetime").datetime.now(),
        boxes=[OverlayBox(x=0, y=0, width=100, height=40, label="measurement_roi")],
        measurements=[AiMeasurement(name="TR Vmax", value="2.1", unit="m/s")],
        raw={
            "line_predictions": [
                {
                    "order": 0,
                    "text": "1 TR Vmax 2.1 m/s",
                    "line_bbox": [5, 8, 80, 20],
                    "uncertain": False,
                }
            ]
        },
    )

    boxes = window._build_viewer_overlay_boxes(result)

    assert len(boxes) == 2
    assert boxes[1].label is not None
    assert boxes[1].label.startswith("L1:")


def test_build_viewer_overlay_boxes_returns_base_boxes_when_debug_disabled() -> None:
    _ = _get_app()
    window = MainWindow()
    window._overlay_mode = "off"
    result = AiResult(
        model_name="demo",
        created_at=__import__("datetime").datetime.now(),
        boxes=[OverlayBox(x=0, y=0, width=100, height=40, label="measurement_roi")],
        measurements=[],
        raw={
            "line_predictions": [
                {
                    "order": 0,
                    "text": "1 TR Vmax 2.1 m/s",
                    "line_bbox": [5, 8, 80, 20],
                    "uncertain": False,
                }
            ]
        },
    )

    boxes = window._build_viewer_overlay_boxes(result)

    assert len(boxes) == 0
