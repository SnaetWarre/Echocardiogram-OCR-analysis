from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.models.types import AiMeasurement, AiResult, OverlayBox
from app.pipeline.measurement_decoder import extract_line_from_source

_STYLE_UNMODIFIED = (
    "QFrame#rowFrame { border: 2px solid #1E8E3E; border-radius: 6px; background: #F4FBF6; }"
)
_STYLE_EDITED = (
    "QFrame#rowFrame { border: 2px solid #0055AA; border-radius: 6px; background: #F0F6FC; }"
)
_STYLE_EMPTY = (
    "QFrame#rowFrame { border: 2px solid #C44; border-radius: 6px; background: #FFF5F5; }"
)


class DragHandleLabel(QtWidgets.QLabel):
    drag_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_start_pos: QtCore.QPoint | None = None
        self.setText("\u2630")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(36)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag to reorder")
        self.setStyleSheet(
            "QLabel {"
            " background-color: #D8E7F6;"
            " color: #123A63;"
            " border: 1px solid #8FB4D8;"
            " border-radius: 4px;"
            " font-weight: 600;"
            " font-size: 16px;"
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
        self.setObjectName("rowFrame")
        self._measurement = measurement

        unit = f" {measurement.unit}" if measurement.unit else ""
        self._ai_text = f"{measurement.name} {measurement.value}{unit}".strip()

        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(10)
        self._drag_handle = DragHandleLabel(self)
        top.addWidget(self._drag_handle, alignment=QtCore.Qt.AlignmentFlag.AlignTop)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)

        ai_label = QtWidgets.QLabel(f"AI detected:  <b>{self._ai_text}</b>")
        ai_label.setWordWrap(True)
        ai_label.setStyleSheet("color: #4B5D70; font-size: 12px; border: none;")
        body.addWidget(ai_label)

        self._raw_ocr_label = QtWidgets.QLabel("")
        self._raw_ocr_label.setWordWrap(True)
        self._raw_ocr_label.setStyleSheet("color: #6B7D90; font-style: italic; font-size: 11px; border: none;")
        source_line = extract_line_from_source(measurement.source)
        if source_line:
            self._raw_ocr_label.setText(f"Source line: {source_line}")
            body.addWidget(self._raw_ocr_label)

        editor_label = QtWidgets.QLabel("Final value (edit if needed):")
        editor_label.setStyleSheet("color: #333; font-weight: 600; font-size: 12px; border: none; margin-top: 2px;")
        body.addWidget(editor_label)

        self._editor = QtWidgets.QPlainTextEdit(self._ai_text)
        self._editor.setTabChangesFocus(True)
        self._editor.setFixedHeight(60)
        self._editor.setPlaceholderText(
            "Type the correct measurement here. One per line.\n"
            "Example: TR Vmax 2.1 m/s"
        )
        self._editor.setStyleSheet(
            "QPlainTextEdit { border: 1px solid #AAA; border-radius: 4px; padding: 4px; font-size: 13px; }"
        )
        self._editor.textChanged.connect(self._on_text_changed)
        body.addWidget(self._editor)

        self._status_label = QtWidgets.QLabel()
        self._status_label.setStyleSheet("border: none;")
        body.addWidget(self._status_label)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(6)

        self._btn_reset = QtWidgets.QPushButton("Reset to AI")
        self._btn_reset.setToolTip("Undo your edits and restore the AI prediction.")
        self._btn_reset.setStyleSheet(
            "QPushButton { background: #E8E8E8; color: #333; border: 1px solid #BBB; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background: #D0D0D0; }"
        )
        self._btn_reset.clicked.connect(self._reset_to_ai)

        self._btn_duplicate = QtWidgets.QToolButton()
        self._btn_duplicate.setText("Duplicate")
        self._btn_duplicate.setToolTip("Duplicate this row (for splitting one OCR result into multiple labels).")
        self._btn_duplicate.setStyleSheet(
            "QToolButton { background: #E8E8E8; border: 1px solid #BBB; border-radius: 4px; padding: 4px 10px; }"
            "QToolButton:hover { background: #D0D0D0; }"
        )
        self._btn_duplicate.clicked.connect(lambda: self.duplicate_requested.emit(self))

        self._btn_remove = QtWidgets.QToolButton()
        self._btn_remove.setText("Remove")
        self._btn_remove.setToolTip("Remove this row entirely.")
        self._btn_remove.setStyleSheet(
            "QToolButton { background: #FDECEA; color: #C44; border: 1px solid #E8A; border-radius: 4px; padding: 4px 10px; }"
            "QToolButton:hover { background: #FBDBD8; }"
        )
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))

        toolbar.addWidget(self._btn_reset)
        toolbar.addWidget(self._btn_duplicate)
        toolbar.addWidget(self._btn_remove)
        toolbar.addStretch(1)
        body.addLayout(toolbar)

        top.addLayout(body, stretch=1)
        layout.addLayout(top)

        self._update_status()

    @property
    def is_edited(self) -> bool:
        return self._editor.toPlainText().strip() != self._ai_text

    @property
    def is_empty(self) -> bool:
        return not self._editor.toPlainText().strip()

    def has_unsaved_edits(self) -> bool:
        return self.is_edited

    def clone(self) -> ValidationFeedbackWidget:
        clone = ValidationFeedbackWidget(self._measurement)
        clone._editor.setPlainText(self._editor.toPlainText())
        return clone

    def _reset_to_ai(self) -> None:
        self._editor.setPlainText(self._ai_text)

    def _on_text_changed(self) -> None:
        self._update_status()
        self.state_changed.emit()

    def _update_status(self) -> None:
        if self.is_empty:
            self._status_label.setText("\u26A0 Empty — this row will be skipped")
            self._status_label.setStyleSheet("color: #C44; font-weight: bold; font-size: 12px; border: none;")
            self._btn_reset.setVisible(True)
            self.setStyleSheet(_STYLE_EMPTY)
        elif self.is_edited:
            self._status_label.setText("\u270F Your edit will be saved")
            self._status_label.setStyleSheet("color: #0055AA; font-weight: bold; font-size: 12px; border: none;")
            self._btn_reset.setVisible(True)
            self.setStyleSheet(_STYLE_EDITED)
        else:
            self._status_label.setText("\u2713 AI prediction accepted — saved as-is")
            self._status_label.setStyleSheet("color: #1E8E3E; font-weight: bold; font-size: 12px; border: none;")
            self._btn_reset.setVisible(False)
            self.setStyleSheet(_STYLE_UNMODIFIED)

    def collect(self) -> list[str]:
        text = self._editor.toPlainText().strip()
        if not text:
            return []

        if text == self._ai_text:
            return [self._ai_text]

        normalized_text = text.replace("\\n", "\n")
        return [line for line in normalized_text.splitlines() if line.strip()]


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
    submitted = QtCore.Signal(object, object, int, int, bool)

    def __init__(
        self,
        dicom_path: Path,
        ai_result: AiResult,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dicom_path = dicom_path
        self._rows: list[ValidationFeedbackWidget] = []
        self._roi_box = self._find_roi_box(ai_result)

        self.setWindowTitle("OCR Validation[*]")
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setWindowFlag(QtCore.Qt.WindowType.Tool, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(720, 820)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QtWidgets.QLabel(
            "<b>Review each measurement below.</b> "
            "The text in each box is exactly what will be saved. "
            "Edit it directly if the AI got it wrong."
        )
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px;")
        layout.addWidget(title)

        roi_summary = self._build_roi_summary()
        if roi_summary is not None:
            layout.addWidget(roi_summary)

        comparison_summary = self._build_engine_comparison_summary(ai_result)
        if comparison_summary is not None:
            layout.addWidget(comparison_summary)

        if not ai_result.boxes:
            warning = QtWidgets.QLabel(
                "No measurement box was detected for this image. "
                "If the OCR result is a false positive, use 'No Measurement Box / Skip File'."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #995700; font-weight: bold;")
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
        self._submit_button = QtWidgets.QPushButton("Submit && Next")
        self._submit_button.setDefault(True)
        self._submit_button.setStyleSheet(
            "QPushButton { background-color: #1E8E3E; color: white; font-weight: bold;"
            " padding: 8px 20px; border-radius: 6px; font-size: 14px; }"
            "QPushButton:hover { background-color: #177332; }"
        )
        self._submit_button.clicked.connect(self._submit)
        button_row.addWidget(self._skip_false_positive_button)
        button_row.addStretch(1)
        button_row.addWidget(self._submit_button)
        layout.addLayout(button_row)

        submit_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self)
        submit_shortcut.activated.connect(self._submit)
        duplicate_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self)
        duplicate_shortcut.activated.connect(self._duplicate_selected_row)
        remove_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Backspace"), self)
        remove_shortcut.activated.connect(self._remove_selected_row)

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

    def _selected_row(self) -> ValidationFeedbackWidget | None:
        item = self._list.currentItem()
        if item is None:
            return self._rows[0] if self._rows else None
        widget = self._list.itemWidget(item)
        return widget if isinstance(widget, ValidationFeedbackWidget) else None

    def _duplicate_selected_row(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._duplicate_row(row)

    def _remove_selected_row(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._remove_row(row)

    def _duplicate_row(self, row_obj: object) -> None:
        if not isinstance(row_obj, ValidationFeedbackWidget):
            return
        self._sync_rows_from_list()
        try:
            index = self._rows.index(row_obj)
        except ValueError:
            index = len(self._rows) - 1
        clone = row_obj.clone()
        self._append_row(clone, index + 1)
        self._mark_dialog_dirty()

    def _remove_row(self, row_obj: object) -> None:
        if not isinstance(row_obj, ValidationFeedbackWidget):
            return
        if len(self._rows) <= 1:
            row_obj._editor.setPlainText("")
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

    def _find_roi_box(self, ai_result: AiResult) -> OverlayBox | None:
        for box in ai_result.boxes:
            if box.label == "measurement_roi":
                return box
        return ai_result.boxes[0] if ai_result.boxes else None

    def _build_roi_summary(self) -> QtWidgets.QFrame | None:
        if self._roi_box is None:
            return None

        box = self._roi_box
        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #F4F8FC; border: 1px solid #C9D7E6; border-radius: 6px; padding: 8px; }"
            "QLabel { color: #1D2A36; }"
        )

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        title = QtWidgets.QLabel("<b>Detected ROI</b>")
        layout.addWidget(title)

        summary = (
            f"x={int(box.x)}, y={int(box.y)}, "
            f"width={int(box.width)}, height={int(box.height)}"
        )
        layout.addWidget(QtWidgets.QLabel(summary))

        if box.confidence is not None:
            layout.addWidget(QtWidgets.QLabel(f"confidence={box.confidence:.3f}"))

        hint = QtWidgets.QLabel(
            "Use this ROI summary to verify that the OCR was taken from the correct measurement box."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #4B5B6B;")
        layout.addWidget(hint)

        return frame

    _ENGINE_COLORS: dict[str, str] = {
        "glm-ocr": "#C2410C",
        "surya": "#B45309",
        "paddleocr": "#1D4ED8",
        "easyocr": "#047857",
        "tesseract": "#6D28D9",
    }

    def _build_engine_comparison_summary(self, ai_result: AiResult) -> QtWidgets.QFrame | None:
        comparison_rows = ai_result.raw.get("engine_comparison")
        formatted_html = self._format_engine_comparison_html(comparison_rows)
        if not formatted_html:
            return None

        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #F7F5EF; border: 1px solid #D8CBA8; border-radius: 6px; padding: 8px; }"
            "QLabel { color: #3E3420; }"
        )

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        title = QtWidgets.QLabel("<b>OCR engine comparison</b>")
        title.setToolTip("When multiple OCR engines are selected, compare their extracted lines here.")
        layout.addWidget(title)

        summary = QtWidgets.QTextEdit()
        summary.setReadOnly(True)
        summary.setHtml(formatted_html)
        summary.setMinimumHeight(120)
        summary.setMaximumHeight(260)
        layout.addWidget(summary)
        return frame

    @classmethod
    def _format_engine_comparison_html(cls, rows: object) -> str:
        if not isinstance(rows, list) or not rows:
            return ""

        parts: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            engine = str(row.get("engine", "unknown")).strip() or "unknown"
            status = str(row.get("status", "unknown")).strip() or "unknown"
            color = cls._ENGINE_COLORS.get(engine.lower(), "#3E3420")
            parts.append(
                f'<div style="margin-bottom:8px;">'
                f'<b style="color:{color};">[{engine}]</b>'
                f' <span style="color:#777;">status={status}</span>'
            )
            error = str(row.get("error", "")).strip()
            if error:
                parts.append(f'<br><span style="color:#C44;">error: {error}</span></div>')
                continue
            exact_lines = row.get("exact_lines")
            if isinstance(exact_lines, list) and exact_lines:
                for line in exact_lines:
                    escaped = str(line).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    parts.append(f'<br><span style="color:{color}; font-family:monospace;">{escaped}</span>')
            else:
                parts.append('<br><span style="color:#999;">No measurements found.</span>')
            parts.append("</div>")
        return "".join(parts)

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
        return any(row.is_edited for row in self._rows)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._has_unsaved_changes():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved changes?",
                "You have edited measurements that haven't been submitted yet.\n\n"
                "Close and LOSE your edits?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    def _submit(self) -> None:
        self._sync_rows_from_list()

        validated: list[str] = []
        approved_count = 0
        edited_count = 0
        edits_detail: list[tuple[str, str]] = []

        for row in self._rows:
            try:
                measurements = row.collect()
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(self, "Invalid measurement", str(exc))
                return

            if row.is_edited:
                edited_count += 1
                edits_detail.append((row._ai_text, row._editor.toPlainText().strip()))
            else:
                approved_count += 1

            validated.extend(measurements)

        summary_lines = [
            f"<b>{approved_count}</b> measurement(s) accepted from AI (unchanged)",
            f"<b>{edited_count}</b> measurement(s) edited by you",
        ]

        if edits_detail:
            summary_lines.append("")
            summary_lines.append("<b>Your edits:</b>")
            for ai_text, your_text in edits_detail:
                summary_lines.append(
                    f'&nbsp;&nbsp;AI: <span style="color:#888">{ai_text}</span><br>'
                    f'&nbsp;&nbsp;You: <span style="color:#0055AA; font-weight:bold">{your_text}</span>'
                )

        summary_lines.append("")
        summary_lines.append(f"<b>Total measurements to save: {len(validated)}</b>")

        confirm = QtWidgets.QMessageBox(self)
        confirm.setWindowTitle("Confirm Submission")
        confirm.setTextFormat(QtCore.Qt.TextFormat.RichText)
        confirm.setText("<br>".join(summary_lines))
        confirm.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Ok)
        confirm.button(QtWidgets.QMessageBox.StandardButton.Ok).setText("Save && Next")
        confirm.button(QtWidgets.QMessageBox.StandardButton.Cancel).setText("Go Back")

        if confirm.exec() != QtWidgets.QMessageBox.StandardButton.Ok:
            return

        self.submitted.emit(self._dicom_path, validated, approved_count, edited_count, False)
        self.setWindowModified(False)
        self.accept()

    def _submit_false_positive(self) -> None:
        incorrect_count = len(self._rows)
        self.setWindowModified(False)
        self.submitted.emit(self._dicom_path, [], 0, incorrect_count, True)
        self.accept()
