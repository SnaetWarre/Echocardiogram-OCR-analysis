from __future__ import annotations

import csv
import io
from dataclasses import asdict
from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from app.models.types import AiResult, DicomSeries

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

        if getattr(self._state, "ai_enabled", False):
            self.addTab(self._tab_ai, "AI Results")

        self._state.series_loaded.connect(self._update_metadata)
        self._state.ai_result_ready.connect(self._update_ai_result)

    def _update_metadata(self, series: DicomSeries) -> None:
        patient = asdict(series.patient)
        metadata = asdict(series.metadata)

        self._tab_patient.setPlainText("\n".join(f"{k}: {v}" for k, v in patient.items() if v))
        self._tab_series.setPlainText("\n".join(f"{k}: {v}" for k, v in metadata.items() if v))
        self._tab_technical.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in metadata.get("additional", {}).items())
        )
        self._ai_table.setRowCount(0)
        self._ai_raw.setPlainText("")

    def _update_ai_result(self, result: AiResult) -> None:
        validated_lines = result.raw.get("validated_lines")
        if isinstance(validated_lines, list):
            self._ai_table.setRowCount(len(validated_lines))
            for row, line in enumerate(validated_lines):
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
                    if isinstance(validated_lines, list):
                        for line in validated_lines:
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
                if isinstance(validated_lines, list):
                    if not validated_lines:
                        buffer.write("  No measurements found.\n")
                    else:
                        for line in validated_lines:
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
