from __future__ import annotations

import re
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.models.types import AiMeasurement, AiResult
from app.pipeline.measurement_parsers import RegexMeasurementParser

_VALUE_UNIT_RE = re.compile(r"^\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>\S+)?\s*$")


class DragHandleLabel(QtWidgets.QLabel):
    drag_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_start_pos: QtCore.QPoint | None = None
        self.setText("Drag")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(52)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Grab here and drag this measurement row to reorder it.")
        self.setStyleSheet(
            "QLabel {"
            " background-color: #D8E7F6;"
            " color: #123A63;"
            " border: 1px solid #8FB4D8;"
            " border-radius: 4px;"
            " font-weight: 600;"
            " padding: 6px 4px;"
            "}"
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            self._drag_start_pos = event.position().toPoint()
        distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
        if distance >= QtWidgets.QApplication.startDragDistance():
            self.drag_requested.emit()
            self._drag_start_pos = None
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_start_pos = None
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class ValidationFeedbackWidget(QtWidgets.QFrame):
    state_changed = QtCore.Signal()
    duplicate_requested = QtCore.Signal(object)
    remove_requested = QtCore.Signal(object)

    def __init__(self, measurement: AiMeasurement, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._measurement = measurement
        self._parser = RegexMeasurementParser()

        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #C8D4E3; border-radius: 6px; }")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(10)
        self._drag_handle = DragHandleLabel(self)
        top.addWidget(self._drag_handle, alignment=QtCore.Qt.AlignmentFlag.AlignTop)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        unit = f" {measurement.unit}" if measurement.unit else ""
        self._title = QtWidgets.QLabel(f"AI Prediction: {measurement.name} {measurement.value}{unit}")
        self._title.setWordWrap(True)

        toolbar = QtWidgets.QHBoxLayout()
        self._btn_approve = QtWidgets.QPushButton("Approve")
        self._btn_wrong = QtWidgets.QPushButton("Wrong / Correct")
        self._btn_duplicate = QtWidgets.QToolButton()
        self._btn_duplicate.setText("Duplicate")
        self._btn_duplicate.setToolTip("Duplicate this row so you can split one OCR result into multiple labels.")
        self._btn_remove = QtWidgets.QToolButton()
        self._btn_remove.setText("Remove")
        self._btn_remove.setToolTip("Remove this row from the review list.")

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

        self._btn_duplicate.clicked.connect(lambda: self.duplicate_requested.emit(self))
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))

        toolbar.addWidget(self._btn_approve)
        toolbar.addWidget(self._btn_wrong)
        toolbar.addWidget(self._btn_duplicate)
        toolbar.addWidget(self._btn_remove)
        toolbar.addStretch(1)

        base_value = f"{measurement.name} {measurement.value}{unit}".strip()
        self._correct_input = QtWidgets.QPlainTextEdit(base_value)
        self._correct_input.setTabChangesFocus(True)
        self._correct_input.setFixedHeight(92)
        self._correct_input.setEnabled(False)
        self._correct_input.setPlaceholderText(
            "Use one line per measurement. Example:\nTR Vmax 2.1 m/s\nTR maxPG 18 mmHg"
        )
        self._correct_input.textChanged.connect(self.state_changed)

        body.addWidget(self._title)
        body.addLayout(toolbar)
        body.addWidget(self._correct_input)
        top.addLayout(body, stretch=1)
        layout.addLayout(top)

    @property
    def is_approved(self) -> bool:
        return self._btn_approve.isChecked()

    def has_unsaved_edits(self) -> bool:
        if self.is_approved:
            return False
        current = self._correct_input.toPlainText().strip()
        unit = f" {self._measurement.unit}" if self._measurement.unit else ""
        original = f"{self._measurement.name} {self._measurement.value}{unit}".strip()
        return current != original

    def clone(self) -> ValidationFeedbackWidget:
        clone = ValidationFeedbackWidget(self._measurement)
        clone._btn_approve.setChecked(self._btn_approve.isChecked())
        clone._btn_wrong.setChecked(self._btn_wrong.isChecked())
        clone._correct_input.setPlainText(self._correct_input.toPlainText())
        clone._correct_input.setEnabled(self._correct_input.isEnabled())
        return clone

    def _on_mode_toggled(self, button: QtWidgets.QAbstractButton, checked: bool) -> None:
        if button is self._btn_wrong:
            self._correct_input.setEnabled(checked)
        self.state_changed.emit()

    def collect(self) -> list[AiMeasurement]:
        if self.is_approved:
            return [self._measurement]
        corrected_text = self._correct_input.toPlainText().strip()
        if not corrected_text:
            return []

        normalized_text = corrected_text.replace("\\n", "\n")
        parsed = self._parser.parse(normalized_text, confidence=1.0)
        if parsed:
            return [
                AiMeasurement(
                    name=item.name,
                    value=item.value,
                    unit=item.unit,
                    source="human_validated",
                    order_hint=item.order_hint,
                )
                for item in parsed
            ]

        single_line = normalized_text.replace("\n", " ").strip()
        match = _VALUE_UNIT_RE.fullmatch(single_line)
        if match is None:
            raise ValueError(
                f"Invalid correction for '{self._measurement.name}'. "
                "Use '<value> <unit>', '<name> <value> <unit>', or multiple entries on separate lines."
            )
        value = match.group("value").replace(",", ".")
        unit = (match.group("unit") or "").strip() or None
        return [
            AiMeasurement(
                name=self._measurement.name,
                value=value,
                unit=unit,
                source="human_validated",
                order_hint=self._measurement.order_hint,
            )
        ]


class ValidationListWidget(QtWidgets.QListWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(8)
        self.setAlternatingRowColors(False)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            "QListWidget::item { border: none; } "
            "QListWidget::item:selected { background: rgba(0,0,0,0.04); }"
        )

    def start_drag_for_widget(self, widget: QtWidgets.QWidget) -> None:
        if self.count() <= 1:
            return
        for index in range(self.count()):
            item = self.item(index)
            if self.itemWidget(item) is widget:
                self.setCurrentItem(item)
                item.setSelected(True)
                self.startDrag(QtCore.Qt.DropAction.MoveAction)
                return

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        super().dropEvent(event)
        dialog = self.parent()
        while dialog is not None and not isinstance(dialog, ValidationDialog):
            dialog = dialog.parent()
        if isinstance(dialog, ValidationDialog):
            dialog._sync_rows_from_list()


class ValidationDialog(QtWidgets.QDialog):
    submitted = QtCore.Signal(object, object, int, int, bool)  # path, measurements, approved, incorrect, skip_output

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
        self.resize(720, 820)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QtWidgets.QLabel(
            "Review AI measurements while keeping the DICOM image visible. "
            "Drag rows to reorder, duplicate rows to split OCR output, and write one measurement per line when correcting."
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        hint = QtWidgets.QLabel(
            "Workflow: 1) Drag into order. 2) Approve good rows. 3) Use Wrong / Correct for edits. "
            "4) Use Duplicate to split one OCR row into multiple labels."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #335C85;")
        layout.addWidget(hint)

        if not ai_result.boxes:
            warning = QtWidgets.QLabel(
                "No measurement box was detected for this image. "
                "If the OCR result is a false positive, use 'No Measurement Box / Skip File'."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #995700;")
            layout.addWidget(warning)

        self._list = ValidationListWidget(self)
        self._list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)

        for measurement in ai_result.measurements:
            self._append_row(ValidationFeedbackWidget(measurement))

        if not self._rows:
            empty = QtWidgets.QListWidgetItem("No measurements found for this frame.")
            empty.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)

        layout.addWidget(self._list, stretch=1)

        button_row = QtWidgets.QHBoxLayout()
        self._skip_false_positive_button = QtWidgets.QPushButton("No Measurement Box / Skip File")
        self._skip_false_positive_button.clicked.connect(self._submit_false_positive)
        self._submit_button = QtWidgets.QPushButton("Submit & Next")
        self._submit_button.setDefault(True)
        self._submit_button.clicked.connect(self._submit)
        button_row.addWidget(self._skip_false_positive_button)
        button_row.addStretch(1)
        button_row.addWidget(self._submit_button)
        layout.addLayout(button_row)

        submit_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        submit_shortcut.activated.connect(self._submit)

    def _append_row(self, row: ValidationFeedbackWidget, index: int | None = None) -> None:
        row._drag_handle.drag_requested.connect(lambda current=row: self._list.start_drag_for_widget(current))
        row.duplicate_requested.connect(self._duplicate_row)
        row.remove_requested.connect(self._remove_row)
        row.state_changed.connect(self._mark_dialog_dirty)

        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        if index is None or index >= self._list.count():
            self._rows.append(row)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        else:
            self._rows.insert(index, row)
            self._list.insertItem(index, item)
            self._list.setItemWidget(item, row)

    def _mark_dialog_dirty(self) -> None:
        self.setWindowModified(True)

    def _duplicate_row(self, row_obj: object) -> None:
        if not isinstance(row_obj, ValidationFeedbackWidget):
            return
        self._sync_rows_from_list()
        try:
            index = self._rows.index(row_obj)
        except ValueError:
            index = len(self._rows) - 1
        clone = row_obj.clone()
        clone._btn_wrong.setChecked(True)
        self._append_row(clone, index + 1)
        self._mark_dialog_dirty()

    def _remove_row(self, row_obj: object) -> None:
        if not isinstance(row_obj, ValidationFeedbackWidget):
            return
        if len(self._rows) <= 1:
            row_obj._btn_wrong.setChecked(True)
            row_obj._correct_input.setPlainText("")
            self._mark_dialog_dirty()
            return

        for index in range(self._list.count()):
            item = self._list.item(index)
            if self._list.itemWidget(item) is row_obj:
                taken = self._list.takeItem(index)
                del taken
                break
        self._sync_rows_from_list()
        self._mark_dialog_dirty()

    def _sync_rows_from_list(self) -> None:
        new_rows: list[ValidationFeedbackWidget] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            widget = self._list.itemWidget(item)
            if isinstance(widget, ValidationFeedbackWidget):
                new_rows.append(widget)
        if new_rows:
            self._rows = new_rows

    def _has_unsaved_changes(self) -> bool:
        return any(row.has_unsaved_edits() for row in self._rows)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._has_unsaved_changes():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved review changes?",
                "You have unsaved corrections in this review dialog. Close anyway?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    def _submit(self) -> None:
        self._sync_rows_from_list()
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
                measurements = row.collect()
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Invalid correction", str(exc))
                return
            validated.extend(measurements)

        self.submitted.emit(self._dicom_path, validated, approved_count, incorrect_count, False)
        self.setWindowModified(False)
        self.accept()

    def _submit_false_positive(self) -> None:
        incorrect_count = len(self._rows)
        self.setWindowModified(False)
        self.submitted.emit(self._dicom_path, [], 0, incorrect_count, True)
        self.accept()
