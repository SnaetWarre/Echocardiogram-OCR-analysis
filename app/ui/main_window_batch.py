from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from app.ui.workers import BatchTestWorker

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


def _show_error(self: "MainWindow", title: str, message: str) -> None:
    self._log_event(f"{title}: {message}")
    self.statusBar().showMessage(message, 5000)
    if self._ui_batch_running:
        return
    if self._suppress_error_dialogs:
        return
    if self._error_dialog_count >= self._max_error_dialogs:
        return
    self._error_dialog_count += 1
    QtWidgets.QMessageBox.critical(self, title, message)


def _log_event(self: "MainWindow", message: str) -> None:
    try:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = self._ui_batch_log_file or self._batch_log_file or self._log_file
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        return


def _start_ui_batch_run(self: "MainWindow") -> None:
    if self._ui_batch_running:
        self._show_error("Batch Run Running", "A UI batch run is already running.")
        return

    root = QtWidgets.QFileDialog.getExistingDirectory(
        self, "Select DICOM Folder", str(Path.cwd())
    )
    if not root:
        return

    root_path = Path(root)
    files = sorted(root_path.rglob("*.dcm")) if root_path.is_dir() else []
    if not files:
        self._show_error("Batch Run", "No DICOM files found in the selected folder.")
        return

    self._ui_batch_paths = files
    self._ui_batch_index = 0
    self._ui_batch_running = True
    self._ui_batch_expect_render = False
    self._ui_batch_ok = 0
    self._ui_batch_fail = 0
    self._ui_batch_start_time = time.perf_counter()
    self._ui_batch_item_start = time.perf_counter()
    self._ui_batch_current_path = None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    self._ui_batch_log_file = self._log_dir / f"dicom_ui_batch_{timestamp}.log"
    self._set_loading_state(True, f"UI batch run started ({len(files)} files)...")
    self._log_event(f"UI batch run started: {root_path} ({len(files)} files)")
    self._ui_batch_next()


def _ui_batch_next(self: "MainWindow") -> None:
    if not self._ui_batch_running:
        return

    total = len(self._ui_batch_paths)
    if self._ui_batch_index >= total:
        self._finish_ui_batch()
        return

    if self._loader_thread and self._loader_thread.isRunning():
        QtCore.QTimer.singleShot(50, self._ui_batch_next)
        return

    path = self._ui_batch_paths[self._ui_batch_index]
    self._ui_batch_current_path = path
    self._ui_batch_item_start = time.perf_counter()
    self.statusBar().showMessage(f"[{self._ui_batch_index + 1}/{total}] Loading {path.name}")
    self._load_dicom(path)


def _log_ui_batch_result(self: "MainWindow", ok: bool, message: str) -> None:
    if not self._ui_batch_current_path:
        return
    total = len(self._ui_batch_paths)
    index = self._ui_batch_index + 1
    duration = time.perf_counter() - self._ui_batch_item_start
    if ok:
        self._ui_batch_ok += 1
        self._log_event(f"[{index}/{total}] OK {self._ui_batch_current_path} {duration:.3f}s")
    else:
        self._ui_batch_fail += 1
        self._log_event(
            f"[{index}/{total}] FAIL {self._ui_batch_current_path} {duration:.3f}s - {message}"
        )


def _finish_ui_batch(self: "MainWindow") -> None:
    duration = time.perf_counter() - self._ui_batch_start_time
    total = len(self._ui_batch_paths)
    log_path = self._ui_batch_log_file or self._log_file
    summary = (
        f"UI batch run finished: {self._ui_batch_ok}/{total} OK, "
        f"{self._ui_batch_fail} failed in {duration:.2f}s\n"
        f"Log file: {log_path}"
    )
    self._log_event(summary)
    self._ui_batch_running = False
    self._ui_batch_paths = []
    self._ui_batch_index = 0
    self._ui_batch_current_path = None
    self._ui_batch_expect_render = False
    self._ui_batch_ok = 0
    self._ui_batch_fail = 0
    self._ui_batch_log_file = None
    self._set_loading_state(False)
    QtWidgets.QMessageBox.information(self, "UI Batch Run Complete", summary)


def _start_batch_test(self: "MainWindow") -> None:
    if self._batch_thread and self._batch_thread.isRunning():
        self._show_error("Batch Test Running", "A batch test is already running.")
        return

    root = QtWidgets.QFileDialog.getExistingDirectory(
        self, "Select DICOM Folder", str(Path.cwd())
    )
    if not root:
        return

    self._set_loading_state(True, f"Batch testing {Path(root).name}...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    self._batch_log_file = self._log_dir / f"dicom_batch_{timestamp}.log"
    self._log_event(f"Batch test started: {root}")

    self._batch_thread = QtCore.QThread(self)
    self._batch_worker = BatchTestWorker(
        Path(root),
        load_pixels=not self._lazy_decode_enabled,
        decode_first_frame=True,
    )
    self._batch_worker.moveToThread(self._batch_thread)
    self._batch_thread.started.connect(self._batch_worker.run)
    self._batch_worker.progress.connect(self._on_batch_progress)
    self._batch_worker.finished.connect(self._on_batch_finished)
    self._batch_worker.finished.connect(self._batch_thread.quit)
    self._batch_worker.finished.connect(self._batch_worker.deleteLater)
    self._batch_thread.finished.connect(self._batch_thread.deleteLater)
    self._batch_thread.start()


def _on_batch_progress(
    self: "MainWindow",
    index: int,
    total: int,
    path: str,
    ok: bool,
    message: str,
    duration: float,
) -> None:
    status = "OK" if ok else "FAIL"
    self.statusBar().showMessage(f"[{index}/{total}] {status} {Path(path).name}")
    if ok:
        self._log_event(f"[{index}/{total}] OK {path} {duration:.3f}s")
    else:
        self._log_event(f"[{index}/{total}] FAIL {path} {duration:.3f}s - {message}")


def _on_batch_finished(self: "MainWindow", ok: int, total: int, duration: float) -> None:
    self._set_loading_state(False)
    self._batch_worker = None
    self._batch_thread = None
    log_path = self._batch_log_file or self._log_file
    summary = f"Batch test finished: {ok}/{total} OK in {duration:.2f}s\nLog file: {log_path}"
    self._log_event(summary)
    self._batch_log_file = None
    QtWidgets.QMessageBox.information(self, "Batch Test Complete", summary)
