from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from app.models.types import AiMeasurement, AiResult
from app.ui.dialogs.validation_dialog import ValidationDialog


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_validation_dialog_prefills_full_measurement_text() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    assert dialog._rows[0]._correct_input.text() == "TR Vmax 1.9 m/s"


def test_validation_dialog_false_positive_submission_emits_skip_flag() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    captured: list[tuple[object, object, int, int, bool]] = []
    dialog.submitted.connect(lambda *args: captured.append(args))

    dialog._submit_false_positive()

    assert len(captured) == 1
    payload = captured[0]
    assert payload[0] == Path("/tmp/example.dcm")
    assert payload[1] == []
    assert payload[2] == 0
    assert payload[3] == 1
    assert payload[4] is True


def test_validation_dialog_accepts_escaped_newlines_for_multiple_measurements() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    row._btn_wrong.click()
    row._correct_input.setPlainText("TR Vmax 1.9 m/s\nTR maxPG 14 mmHg")

    measurements = row.collect()

    assert len(measurements) == 2
    assert measurements[0].name == "TR Vmax"
    assert measurements[1].name == "TR maxPG"


def test_validation_dialog_remove_last_row_clears_it_instead_of_deleting() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    dialog._remove_row(dialog._rows[0])

    assert len(dialog._rows) == 1
    assert dialog._rows[0]._btn_wrong.isChecked()
    assert dialog._rows[0]._correct_input.toPlainText() == ""
