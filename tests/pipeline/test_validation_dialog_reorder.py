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


def test_validation_dialog_allows_manual_reorder() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[
            AiMeasurement(name="First", value="1"),
            AiMeasurement(name="Second", value="2"),
            AiMeasurement(name="Third", value="3"),
        ],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    item = dialog._list.takeItem(2)
    dialog._list.insertItem(0, item)
    dialog._sync_rows_from_list()

    assert [row._measurement.name for row in dialog._rows] == ["Third", "First", "Second"]


def test_validation_dialog_can_duplicate_row() -> None:
    _ = _get_app()
    result = AiResult(
        model_name="demo",
        created_at=datetime.now(),
        measurements=[AiMeasurement(name="Only", value="1")],
    )
    dialog = ValidationDialog(Path("/tmp/example.dcm"), result)

    dialog._duplicate_row(dialog._rows[0])

    assert len(dialog._rows) == 2
    assert dialog._rows[1]._measurement.name == "Only"
    assert dialog._rows[1]._btn_wrong.isChecked()
