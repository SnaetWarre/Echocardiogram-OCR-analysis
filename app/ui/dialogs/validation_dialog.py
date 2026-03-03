from __future__ import annotations

import re
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from app.models.types import AiMeasurement, AiResult
from app.pipeline.measurement_parsers import RegexMeasurementParser

_VALUE_UNIT_RE = re.compile(r"^\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>\S+)?\s*$")


class ValidationFeedbackWidget(QtWidgets.QFrame):
    def __init__(self, measurement: AiMeasurement, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._measurement = measurement
        self._parser = RegexMeasurementParser()

        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        unit = f" {measurement.unit}" if measurement.unit else ""
        self._title = QtWidgets.QLabel(
            f"AI Prediction: {measurement.name} {measurement.value}{unit}"
        )
        self._title.setWordWrap(True)

        actions = QtWidgets.QHBoxLayout()
        self._btn_approve = QtWidgets.QPushButton("Approve")
        self._btn_wrong = QtWidgets.QPushButton("Wrong / Correct")
        self._btn_approve.setCheckable(True)
        self._btn_wrong.setCheckable(True)
        self._btn_approve.setChecked(True)
        self._btn_approve.setStyleSheet("QPushButton { background-color: #1E8E3E; color: white; }")
        self._btn_wrong.setStyleSheet("QPushButton { background-color: #995700; color: white; }")

        self._mode_group = QtWidgets.QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._btn_approve)
        self._mode_group.addButton(self._btn_wrong)
        self._mode_group.buttonToggled.connect(self._on_mode_toggled)

        actions.addWidget(self._btn_approve)
        actions.addWidget(self._btn_wrong)
        actions.addStretch(1)

        base_value = f"{measurement.value}{unit}".strip()
        self._correct_input = QtWidgets.QLineEdit(base_value)
        self._correct_input.setEnabled(False)
        self._correct_input.setPlaceholderText(
            "Correct Result (e.g. 1.2 m/s or TR Vmax 2.1 m/s; leave empty to delete)"
        )

        layout.addWidget(self._title)
        layout.addLayout(actions)
        layout.addWidget(self._correct_input)

    @property
    def is_approved(self) -> bool:
        return self._btn_approve.isChecked()

    def _on_mode_toggled(self, button: QtWidgets.QAbstractButton, checked: bool) -> None:
        if button is self._btn_wrong:
            self._correct_input.setEnabled(checked)

    def collect(self) -> AiMeasurement | None:
        if self.is_approved:
            return self._measurement
        corrected_text = self._correct_input.text().strip()
        if not corrected_text:
            return None
        parsed = self._parser.parse(corrected_text, confidence=1.0)
        if parsed:
            first = parsed[0]
            return AiMeasurement(
                name=first.name,
                value=first.value,
                unit=first.unit,
                source="human_validated",
            )
        match = _VALUE_UNIT_RE.fullmatch(corrected_text)
        if match is None:
            raise ValueError(
                f"Invalid correction for '{self._measurement.name}'. "
                "Use '<value> <unit>' or '<name> <value> <unit>'."
            )
        value = match.group("value").replace(",", ".")
        unit = (match.group("unit") or "").strip() or None
        return AiMeasurement(
            name=self._measurement.name,
            value=value,
            unit=unit,
            source="human_validated",
        )


class ValidationDialog(QtWidgets.QDialog):
    submitted = QtCore.Signal(object, object, int, int)  # path, measurements, approved, incorrect

    def __init__(
        self,
        dicom_path: Path,
        ai_result: AiResult,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dicom_path = dicom_path
        self._rows: list[ValidationFeedbackWidget] = []

        self.setWindowTitle("OCR Validation")
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setWindowFlag(QtCore.Qt.WindowType.Tool, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(520, 620)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Review AI measurements while keeping the DICOM image visible.")
        title.setWordWrap(True)
        layout.addWidget(title)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        for measurement in ai_result.measurements:
            row = ValidationFeedbackWidget(measurement)
            self._rows.append(row)
            scroll_layout.addWidget(row)

        if not self._rows:
            scroll_layout.addWidget(QtWidgets.QLabel("No measurements found for this frame."))

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        self._submit_button = QtWidgets.QPushButton("Submit & Next")
        self._submit_button.setDefault(True)
        self._submit_button.clicked.connect(self._submit)
        layout.addWidget(self._submit_button)

    def _submit(self) -> None:
        validated: list[AiMeasurement] = []
        approved_count = 0
        incorrect_count = 0

        for row in self._rows:
            approved = row.is_approved
            if approved:
                approved_count += 1
            else:
                incorrect_count += 1
            try:
                measurement = row.collect()
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Invalid correction", str(exc))
                return
            if measurement is not None:
                validated.append(measurement)

        self.submitted.emit(self._dicom_path, validated, approved_count, incorrect_count)
        self.accept()
