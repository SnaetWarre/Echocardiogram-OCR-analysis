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

    assert dialog._rows[0]._editor.toPlainText() == "TR Vmax 1.9 m/s"


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


def test_validation_dialog_accepts_newlines_for_multiple_measurements() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    row._editor.setPlainText("TR Vmax 1.9 m/s\nTR maxPG 14 mmHg")

    measurements = row.collect()

    assert len(measurements) == 2
    assert measurements[0] == "TR Vmax 1.9 m/s"
    assert measurements[1] == "TR maxPG 14 mmHg"


def test_validation_dialog_remove_last_row_clears_it() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    dialog._remove_row(dialog._rows[0])

    assert len(dialog._rows) == 1
    assert dialog._rows[0]._editor.toPlainText() == ""


def test_validation_dialog_editing_text_marks_row_as_edited() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="L", value="1.81", unit="cm")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    assert not row.is_edited

    row._editor.setPlainText("L 3.00 cm")

    assert row.is_edited


def test_validation_dialog_collect_uses_edited_text() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="L", value="1.81", unit="cm")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    row._editor.setPlainText("L 3.00 cm")

    measurements = row.collect()

    assert len(measurements) == 1
    assert measurements[0] == "L 3.00 cm"


def test_validation_dialog_collect_preserves_literal_edited_line() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="Ao Desc Diam", value="2.0", unit="cm")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    row._editor.setPlainText("Ao Desc Diam 2.0 cm2")

    measurements = row.collect()

    assert len(measurements) == 1
    assert measurements[0] == "Ao Desc Diam 2.0 cm2"


def test_validation_dialog_collect_returns_original_when_unedited() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="L", value="1.81", unit="cm")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    measurements = row.collect()

    assert len(measurements) == 1
    assert measurements[0] == "L 1.81 cm"


def test_validation_dialog_reset_to_ai_restores_original() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    row = dialog._rows[0]
    row._editor.setPlainText("TR Vmax 2.5 m/s")
    assert row.is_edited

    row._reset_to_ai()

    assert not row.is_edited
    assert row._editor.toPlainText() == "TR Vmax 1.9 m/s"


def test_validation_dialog_shows_engine_comparison_when_present() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")],
        raw={
            "engine_comparison": [
                {"engine": "surya", "status": "ok", "exact_lines": ["1 TR Vmax 1.9 m/s"]},
                {"engine": "easyocr", "status": "ok", "exact_lines": ["1 TR Vmax 2.0 m/s"]},
            ]
        },
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    comparison_texts = [
        widget.toPlainText()
        for widget in dialog.findChildren(QtWidgets.QTextEdit)
        if "surya" in widget.toPlainText() and "easyocr" in widget.toPlainText()
    ]

    assert comparison_texts
