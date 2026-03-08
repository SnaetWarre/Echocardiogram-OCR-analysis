from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DICOM_AI_ENABLED", "0")

from PySide6 import QtWidgets

from app.models.types import AiMeasurement
from app.ui.main_window import MainWindow


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_validation_submit_skips_output_when_false_positive(tmp_path: Path) -> None:
    _ = _get_app()
    window = MainWindow()
    output_path = tmp_path / "validation_labels.md"
    window._validation_writer._output_path = output_path

    window._on_validation_submitted(
        Path("/tmp/example.dcm"),
        [AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
        0,
        1,
        True,
    )

    assert not output_path.exists()
    assert window._state.validation_session.total_validated_frames == 1
    assert window._state.validation_session.total_ai_incorrect == 1
