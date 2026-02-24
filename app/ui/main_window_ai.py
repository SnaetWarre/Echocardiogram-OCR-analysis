from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from app.models.types import AiResult, PipelineRequest
from app.ui.workers import AiRunWorker

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


def _run_ai(self: "MainWindow") -> None:
    if not getattr(self, "_ai_enabled", False) or self._pipeline_manager is None:
        self.statusBar().showMessage("AI is disabled for this session.", 2500)
        return
    if not self._current_path:
        self.statusBar().showMessage("No DICOM loaded.", 2000)
        return
    if self._ai_thread and self._ai_thread.isRunning():
        self.statusBar().showMessage("AI already running.", 2000)
        return

    request = PipelineRequest(dicom_path=self._current_path)
    self.statusBar().showMessage("Running AI pipeline...")
    self._ai_thread = QtCore.QThread(self)
    self._ai_worker = AiRunWorker(self._pipeline_manager, request)
    self._ai_worker.moveToThread(self._ai_thread)
    self._ai_thread.started.connect(self._ai_worker.run)
    self._ai_worker.finished.connect(self._on_ai_finished)
    self._ai_worker.failed.connect(self._on_ai_failed)
    self._ai_worker.finished.connect(self._ai_thread.quit)
    self._ai_worker.failed.connect(self._ai_thread.quit)
    self._ai_worker.finished.connect(self._ai_worker.deleteLater)
    self._ai_worker.failed.connect(self._ai_worker.deleteLater)
    self._ai_thread.finished.connect(self._ai_thread.deleteLater)
    self._ai_thread.start()


def _on_ai_finished(self: "MainWindow", result) -> None:
    self.statusBar().showMessage(f"AI finished: {result.status}", 3000)
    self._ai_worker = None
    self._ai_thread = None

    if result.ai_result is None:
        self._last_ai_result = None
        self._viewer.clear_overlays()
        return

    self._last_ai_result = result.ai_result
    self._apply_ai_result(result.ai_result)


def _on_ai_failed(self: "MainWindow", message: str) -> None:
    self.statusBar().showMessage("AI failed.", 3000)
    self._ai_worker = None
    self._ai_thread = None
    self._show_error("AI Error", f"AI pipeline failed: {message}")


def _apply_ai_result(self: "MainWindow", ai_result: AiResult) -> None:
    self._ai_table.setRowCount(0)
    for measurement in ai_result.measurements:
        row = self._ai_table.rowCount()
        self._ai_table.insertRow(row)
        self._ai_table.setItem(row, 0, QtWidgets.QTableWidgetItem(measurement.name))
        self._ai_table.setItem(row, 1, QtWidgets.QTableWidgetItem(measurement.value))
        self._ai_table.setItem(row, 2, QtWidgets.QTableWidgetItem(measurement.unit or ""))

    self._ai_raw.setPlainText(str(ai_result.raw))
    self._viewer.set_overlay_boxes(ai_result.boxes)


def _export_ai_csv(self: "MainWindow") -> None:
    if not self._last_ai_result:
        self.statusBar().showMessage("No AI results to export.", 2000)
        return

    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self, "Export CSV", "results.csv", "CSV Files (*.csv)"
    )
    if not path:
        return

    lines = ["name,value,unit"]
    for measurement in self._last_ai_result.measurements:
        lines.append(f"{measurement.name},{measurement.value},{measurement.unit or ''}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    self.statusBar().showMessage("CSV exported.", 2000)


def _export_ai_txt(self: "MainWindow") -> None:
    if not self._last_ai_result:
        self.statusBar().showMessage("No AI results to export.", 2000)
        return

    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        self, "Export TXT", "results.txt", "Text Files (*.txt)"
    )
    if not path:
        return

    lines = [
        f"{measurement.name}: {measurement.value} {measurement.unit or ''}".strip()
        for measurement in self._last_ai_result.measurements
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    self.statusBar().showMessage("TXT exported.", 2000)
