from __future__ import annotations

import csv
import io
from dataclasses import asdict
from typing import TYPE_CHECKING

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.models.types import AiResult, DicomSeries, OverlayBox
from app.ocr.preprocessing import preprocess_roi
from app.utils.image import qimage_from_array

if TYPE_CHECKING:
    from app.ui.state import ViewerState


class MetadataTabsWidget(QtWidgets.QTabWidget):
    """Widget displaying patient, series, generic technical, and AI metadata."""

    def __init__(self, state: ViewerState) -> None:
        super().__init__()
        self._state = state
        self.setObjectName("metadataTabs")

        self._tab_patient = QtWidgets.QTextEdit()
        self._tab_patient.setReadOnly(True)
        self.addTab(self._tab_patient, "Patient")

        self._tab_series = QtWidgets.QTextEdit()
        self._tab_series.setReadOnly(True)
        self.addTab(self._tab_series, "Series")

        self._tab_technical = QtWidgets.QTextEdit()
        self._tab_technical.setReadOnly(True)
        self.addTab(self._tab_technical, "Technical")

        self._tab_ai = QtWidgets.QWidget()
        self._tab_ai_layout = QtWidgets.QVBoxLayout(self._tab_ai)
        self._tab_ai_layout.setContentsMargins(8, 8, 8, 8)
        self._tab_ai_layout.setSpacing(8)

        self._ai_table = QtWidgets.QTableWidget(0, 3)
        self._ai_table.setHorizontalHeaderLabels(["Measurement", "Value", "Unit"])
        self._ai_table.horizontalHeader().setStretchLastSection(True)
        self._ai_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tab_ai_layout.addWidget(self._ai_table)

        self._ai_comparison = QtWidgets.QTextEdit()
        self._ai_comparison.setReadOnly(True)
        self._ai_comparison.hide()
        self._tab_ai_layout.addWidget(self._ai_comparison)

        self._ai_raw = QtWidgets.QTextEdit()
        self._ai_raw.setReadOnly(True)
        self._tab_ai_layout.addWidget(self._ai_raw)

        ai_buttons = QtWidgets.QHBoxLayout()
        self._btn_export_csv = QtWidgets.QPushButton("Export CSV")
        self._btn_export_txt = QtWidgets.QPushButton("Export TXT")
        self._btn_export_csv.clicked.connect(self._export_ai_csv)
        self._btn_export_txt.clicked.connect(self._export_ai_txt)
        ai_buttons.addStretch(1)
        ai_buttons.addWidget(self._btn_export_csv)
        ai_buttons.addWidget(self._btn_export_txt)
        self._tab_ai_layout.addLayout(ai_buttons)

        self._tab_roi_preview = QtWidgets.QWidget()
        self._tab_roi_layout = QtWidgets.QVBoxLayout(self._tab_roi_preview)
        self._tab_roi_layout.setContentsMargins(8, 8, 8, 8)
        self._tab_roi_layout.setSpacing(6)

        roi_header = QtWidgets.QHBoxLayout()
        roi_header.setSpacing(8)
        self._roi_info_label = QtWidgets.QLabel("No ROI detected")
        self._roi_info_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        roi_header.addWidget(self._roi_info_label, stretch=1)
        self._roi_view_combo = QtWidgets.QComboBox()
        self._roi_view_combo.addItems(["Raw Crop", "Preprocessed"])
        self._roi_view_combo.setToolTip("Toggle between the raw ROI crop and the preprocessed version the OCR engine receives.")
        self._roi_view_combo.setFixedWidth(140)
        self._roi_view_combo.currentIndexChanged.connect(self._render_roi_preview)
        roi_header.addWidget(self._roi_view_combo)
        self._tab_roi_layout.addLayout(roi_header)

        self._roi_image_label = QtWidgets.QLabel()
        self._roi_image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._roi_image_label.setMinimumHeight(60)
        self._roi_image_label.setStyleSheet("background: #FAFAFA; border: 1px solid #DDD; border-radius: 4px;")
        roi_scroll = QtWidgets.QScrollArea()
        roi_scroll.setWidget(self._roi_image_label)
        roi_scroll.setWidgetResizable(True)
        self._tab_roi_layout.addWidget(roi_scroll, stretch=1)

        self._roi_seg_label = QtWidgets.QLabel("")
        self._roi_seg_label.setWordWrap(True)
        self._roi_seg_label.setStyleSheet("color: #5B6B7B; font-size: 11px;")
        self._tab_roi_layout.addWidget(self._roi_seg_label)

        self._cached_roi_crop: np.ndarray | None = None
        self._cached_roi_preprocessed: np.ndarray | None = None

        if getattr(self._state, "ai_enabled", False):
            self.addTab(self._tab_ai, "AI Results")
            self.addTab(self._tab_roi_preview, "ROI Preview")

        self._state.series_loaded.connect(self._update_metadata)
        self._state.ai_result_ready.connect(self._update_ai_result)
        self._state.ai_result_ready.connect(self._update_roi_from_result)
        self._state.frame_changed.connect(self._on_frame_changed_roi)

    def _update_metadata(self, series: DicomSeries) -> None:
        patient = asdict(series.patient)
        metadata = asdict(series.metadata)

        self._tab_patient.setPlainText("\n".join(f"{k}: {v}" for k, v in patient.items() if v))
        self._tab_series.setPlainText("\n".join(f"{k}: {v}" for k, v in metadata.items() if v))
        self._tab_technical.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in metadata.get("additional", {}).items())
        )
        self._ai_table.setRowCount(0)
        self._ai_comparison.clear()
        self._ai_comparison.hide()
        self._ai_raw.setPlainText("")
        self._clear_roi_preview()

    def _update_ai_result(self, result: AiResult) -> None:
        comparison_rows = result.raw.get("engine_comparison")
        comparison_text = self._format_engine_comparison(comparison_rows)
        if comparison_text:
            self._ai_comparison.setPlainText(comparison_text)
            self._ai_comparison.show()
        else:
            self._ai_comparison.clear()
            self._ai_comparison.hide()

        validated_lines = result.raw.get("validated_lines")
        exact_lines = result.raw.get("exact_lines")
        line_rows = validated_lines if isinstance(validated_lines, list) else exact_lines if isinstance(exact_lines, list) else None
        if isinstance(line_rows, list):
            self._ai_table.setRowCount(len(line_rows))
            for row, line in enumerate(line_rows):
                text = line if isinstance(line, str) else str(line)
                self._ai_table.setItem(row, 0, QtWidgets.QTableWidgetItem(text))
                self._ai_table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
                self._ai_table.setItem(row, 2, QtWidgets.QTableWidgetItem(""))
        else:
            self._ai_table.setRowCount(len(result.measurements))
            for row, measurement in enumerate(result.measurements):
                self._ai_table.setItem(row, 0, QtWidgets.QTableWidgetItem(measurement.name))
                self._ai_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(measurement.value)))
                unit_str = measurement.unit if measurement.unit else ""
                self._ai_table.setItem(row, 2, QtWidgets.QTableWidgetItem(unit_str))
        self._ai_raw.setPlainText(str(result.raw))

    @staticmethod
    def _format_engine_comparison(rows: object) -> str:
        if not isinstance(rows, list) or not rows:
            return ""

        blocks: list[str] = ["OCR engine comparison"]
        for row in rows:
            if not isinstance(row, dict):
                continue
            engine = str(row.get("engine", "unknown")).strip() or "unknown"
            status = str(row.get("status", "unknown")).strip() or "unknown"
            blocks.append(f"\n[{engine}] status={status}")
            error = str(row.get("error", "")).strip()
            if error:
                blocks.append(f"error: {error}")
                continue
            exact_lines = row.get("exact_lines")
            if isinstance(exact_lines, list) and exact_lines:
                blocks.extend(str(line) for line in exact_lines)
                continue
            measurements = row.get("measurements")
            if isinstance(measurements, list) and measurements:
                for measurement in measurements:
                    if not isinstance(measurement, dict):
                        continue
                    name = str(measurement.get("name", "")).strip()
                    value = str(measurement.get("value", "")).strip()
                    unit = str(measurement.get("unit", "")).strip()
                    line = " ".join(part for part in (name, value, unit) if part)
                    if line:
                        blocks.append(line)
            else:
                blocks.append("No measurements found.")
        return "\n".join(blocks).strip()

    # --- ROI Preview ---

    def _find_roi_box(self, result: AiResult) -> OverlayBox | None:
        for box in result.boxes:
            if box.label == "measurement_roi":
                return box
        return result.boxes[0] if result.boxes else None

    def _clear_roi_preview(self) -> None:
        self._cached_roi_crop = None
        self._cached_roi_preprocessed = None
        self._roi_info_label.setText("No ROI detected")
        self._roi_seg_label.setText("")
        self._roi_image_label.clear()

    def _on_frame_changed_roi(self, _frame_index: int) -> None:
        if self._state.last_ai_result is None:
            return
        self._update_roi_from_result(self._state.last_ai_result)

    def _update_roi_from_result(self, result: AiResult) -> None:
        series = self._state.series
        if series is None:
            self._clear_roi_preview()
            return
        roi_box = self._find_roi_box(result)
        if roi_box is None or roi_box.width <= 0 or roi_box.height <= 0:
            self._clear_roi_preview()
            return

        try:
            frame = series.get_frame(self._state.frame_index)
        except Exception:
            self._clear_roi_preview()
            return

        x, y = int(roi_box.x), int(roi_box.y)
        w, h = int(roi_box.width), int(roi_box.height)
        fh, fw = frame.shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = min(w, fw - x)
        h = min(h, fh - y)
        if w <= 0 or h <= 0:
            self._clear_roi_preview()
            return

        roi = frame[y : y + h, x : x + w]
        self._cached_roi_crop = roi.copy()
        self._cached_roi_preprocessed = None

        seg_mode = result.raw.get("segmentation_mode", "unknown")
        line_h = result.raw.get("target_line_height_px", "?")
        self._roi_info_label.setText(f"ROI: x={x}, y={y}, {w}\u00d7{h}")
        self._roi_seg_label.setText(f"Segmentation: {seg_mode}, target line height: {line_h}px")

        self._render_roi_preview()

    def _render_roi_preview(self) -> None:
        show_preprocessed = self._roi_view_combo.currentIndex() == 1

        if show_preprocessed:
            if self._cached_roi_preprocessed is None and self._cached_roi_crop is not None:
                try:
                    self._cached_roi_preprocessed = preprocess_roi(self._cached_roi_crop)
                except Exception:
                    self._cached_roi_preprocessed = self._cached_roi_crop
            source = self._cached_roi_preprocessed
        else:
            source = self._cached_roi_crop

        if source is None:
            self._roi_image_label.clear()
            return

        qimg = qimage_from_array(source)
        pixmap = QtGui.QPixmap.fromImage(qimg)
        available_width = self._roi_image_label.width() or 400
        if pixmap.width() > available_width:
            pixmap = pixmap.scaledToWidth(
                available_width, QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        elif pixmap.width() < 200 and available_width > 200:
            scale_to = min(available_width, pixmap.width() * 3)
            pixmap = pixmap.scaledToWidth(
                scale_to, QtCore.Qt.TransformationMode.FastTransformation,
            )
        self._roi_image_label.setPixmap(pixmap)

    def _export_ai_csv(self) -> None:
        result = self._state.last_ai_result
        if not result:
            QtWidgets.QMessageBox.warning(self, "Export Failed", "No AI results to export.")
            return

        dialog = QtWidgets.QFileDialog(self, "Export CSV")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix("csv")
        dialog.setNameFilter("CSV Files (*.csv)")
        dialog.setOption(QtWidgets.QFileDialog.Option.DontConfirmOverwrite, False)

        if dialog.exec() == int(QtWidgets.QDialog.DialogCode.Accepted):
            path = dialog.selectedFiles()[0]
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Measurement", "Value", "Unit"])
                    validated_lines = result.raw.get("validated_lines")
                    exact_lines = result.raw.get("exact_lines")
                    line_rows = validated_lines if isinstance(validated_lines, list) else exact_lines if isinstance(exact_lines, list) else None
                    if isinstance(line_rows, list):
                        for line in line_rows:
                            writer.writerow([line, "", ""])
                    else:
                        for meas in result.measurements:
                            writer.writerow([meas.name, meas.value, meas.unit])
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def _export_ai_txt(self) -> None:
        result = self._state.last_ai_result
        if not result:
            QtWidgets.QMessageBox.warning(self, "Export Failed", "No AI results to export.")
            return

        dialog = QtWidgets.QFileDialog(self, "Export Report")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix("txt")
        dialog.setNameFilter("Text Files (*.txt)")
        dialog.setOption(QtWidgets.QFileDialog.Option.DontConfirmOverwrite, False)

        if dialog.exec() == int(QtWidgets.QDialog.DialogCode.Accepted):
            path = dialog.selectedFiles()[0]
            try:
                buffer = io.StringIO()
                buffer.write(f"AI Report - {result.model_name}\n")
                buffer.write("=" * 40 + "\n\n")

                if self._state.series:
                    s = self._state.series
                    p = s.patient
                    buffer.write("Patient Information:\n")
                    buffer.write(f"  Name: {p.name or 'Unknown'}\n")
                    buffer.write(f"  ID: {p.patient_id or 'Unknown'}\n")
                    buffer.write("\nStudy Information:\n")
                    buffer.write(f"  Date: {p.study_date or 'Unknown'}\n")
                    buffer.write(f"  Desc: {p.study_description or 'Unknown'}\n")
                    buffer.write(f"  Series: {p.series_description or 'Unknown'}\n")
                    buffer.write("-" * 40 + "\n\n")

                buffer.write("Measurements:\n")
                validated_lines = result.raw.get("validated_lines")
                exact_lines = result.raw.get("exact_lines")
                line_rows = validated_lines if isinstance(validated_lines, list) else exact_lines if isinstance(exact_lines, list) else None
                if isinstance(line_rows, list):
                    if not line_rows:
                        buffer.write("  No measurements found.\n")
                    else:
                        for line in line_rows:
                            buffer.write(f"  {line}\n")
                elif not result.measurements:
                    buffer.write("  No measurements found.\n")
                else:
                    for meas in result.measurements:
                        unit = f" {meas.unit}" if meas.unit else ""
                        buffer.write(f"  {meas.name}: {meas.value}{unit}\n")
                buffer.write("\n")

                with open(path, "w", encoding="utf-8") as f:
                    f.write(buffer.getvalue())
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Export Error", str(e))
