from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtWidgets

from app.io.dicom_loader import DicomLoadError, load_dicom_series
from app.models.types import DicomSeries
from app.ui.workers import DicomLoadWorker, PrefetchTask
from app.utils.image import qimage_from_array

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


def _update_status(self: "MainWindow") -> None:
    name = self._current_path.name if self._current_path else "No file"
    self._status_file.setText(name)
    total = self._series.frame_count if self._series else 0
    frame_text = f"Frame {self._frame_index + 1}/{total}" if total else "Frame 0/0"
    self._status_frame.setText(frame_text)
    self._frame_label.setText(frame_text)
    self._status_fps.setText(f"FPS {self._fps:.2f}")
    stats = self._frame_cache.stats()
    self._status_cache.setText(f"Cache {stats.size}/{stats.capacity}")


def _on_view_changed(self: "MainWindow", zoom: float) -> None:
    _ = zoom
    self._update_status()


def _on_search_changed(self: "MainWindow", text: str) -> None:
    self._proxy_model.set_search_text(text)


def _on_filter_changed(self: "MainWindow") -> None:
    checked = self._filter_toggle.isChecked()
    self._proxy_model.set_show_dcm_only(checked)
    self._btn_slim_filter.blockSignals(True)
    self._btn_slim_filter.setChecked(checked)
    self._btn_slim_filter.blockSignals(False)
    if hasattr(self, "_act_filter"):
        self._act_filter.blockSignals(True)
        self._act_filter.setChecked(checked)
        self._act_filter.blockSignals(False)


def _toggle_filter(self: "MainWindow") -> None:
    self._filter_toggle.setChecked(not self._filter_toggle.isChecked())


def _open_folder(self: "MainWindow") -> None:
    folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", str(Path.cwd()))
    if not folder:
        return
    self._set_tree_root(Path(folder))


def _open_file(self: "MainWindow") -> None:
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        self, "Select DICOM File", str(Path.cwd()), "DICOM Files (*.dcm);;All Files (*.*)"
    )
    if not file_path:
        return
    self._load_dicom(Path(file_path))


def _set_tree_root(self: "MainWindow", path: Path) -> None:
    self._fs_model.setRootPath(str(path))
    source_index = self._fs_model.index(str(path))
    self._tree.setRootIndex(self._proxy_model.mapFromSource(source_index))


def _tree_double_clicked(self: "MainWindow", index: QtCore.QModelIndex) -> None:
    source_index = self._proxy_model.mapToSource(index)
    path = Path(self._fs_model.filePath(source_index))
    if path.is_dir():
        self._set_tree_root(path)
        return
    self._load_dicom(path)


def _toggle_sidebar(self: "MainWindow") -> None:
    self._set_sidebar_collapsed(not self._sidebar_collapsed)


def _set_sidebar_collapsed(self: "MainWindow", collapsed: bool) -> None:
    self._sidebar_collapsed = collapsed
    if collapsed:
        self._left_stack.setCurrentWidget(self._sidebar_slim)
        self._left_panel.setMinimumWidth(56)
        self._left_panel.setMaximumWidth(56)
        self._btn_toggle_sidebar.setText("Expand Sidebar")
        self._btn_toggle_sidebar.setIcon(self._icon("sidebar_expand"))
        if hasattr(self, "_act_toggle_sidebar"):
            self._act_toggle_sidebar.setText("Expand Sidebar")
            self._act_toggle_sidebar.setIcon(self._icon("sidebar_expand"))
    else:
        self._left_stack.setCurrentWidget(self._left_full)
        self._left_panel.setMinimumWidth(260)
        self._left_panel.setMaximumWidth(16777215)
        self._btn_toggle_sidebar.setText("Collapse Sidebar")
        self._btn_toggle_sidebar.setIcon(self._icon("sidebar_collapse"))
        if hasattr(self, "_act_toggle_sidebar"):
            self._act_toggle_sidebar.setText("Collapse Sidebar")
            self._act_toggle_sidebar.setIcon(self._icon("sidebar_collapse"))


def _set_loading_state(self: "MainWindow", loading: bool, message: Optional[str] = None) -> None:
    widgets = (
        self._btn_prev,
        self._btn_play,
        self._btn_next,
        self._slider,
        self._btn_toggle_sidebar,
        self._tree,
        self._filter_toggle,
        self._search,
        self._btn_slim_expand,
        self._btn_slim_open_file,
        self._btn_slim_open_folder,
        self._btn_slim_filter,
    )
    for widget in widgets:
        if widget is not None:
            widget.setEnabled(not loading)

    if loading:
        self._timer.stop()
        self._playing = False
        self._btn_play.setText("Play")
        self._btn_play.setIcon(self._icon("play"))
        if message:
            self.statusBar().showMessage(message)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
    else:
        QtWidgets.QApplication.restoreOverrideCursor()


def _load_dicom(self: "MainWindow", path: Path) -> None:
    if not path.exists():
        self.statusBar().showMessage(f"File not found: {path}", 3000)
        return

    if self._load_on_main_thread:
        self._set_loading_state(True, f"Loading {path.name}...")
        try:
            series = load_dicom_series(path, load_pixels=not self._lazy_decode_enabled)
        except DicomLoadError as exc:
            if not self._ui_batch_running:
                self._set_loading_state(False)
                self._show_error("Load Error", str(exc))
                return
            self._log_ui_batch_result(False, str(exc))
            self._ui_batch_index += 1
            QtCore.QTimer.singleShot(0, self._ui_batch_next)
            return
        if not self._ui_batch_running:
            self._set_loading_state(False)
        self._apply_loaded_series(series)
        return

    if self._loader_thread and self._loader_thread.isRunning():
        self.statusBar().showMessage("Already loading a DICOM file.", 2000)
        return

    self._set_loading_state(True, f"Loading {path.name}...")
    self._loader_thread = QtCore.QThread(self)
    self._loader = DicomLoadWorker(path, load_pixels=not self._lazy_decode_enabled)
    self._loader.moveToThread(self._loader_thread)
    self._loader_thread.started.connect(self._loader.run)
    self._loader.finished.connect(self._on_load_finished)
    self._loader.finished.connect(self._loader_thread.quit)
    self._loader.finished.connect(self._loader.deleteLater)
    self._loader_thread.finished.connect(self._loader_thread.deleteLater)
    self._loader_thread.start()


def _on_load_finished(
    self: "MainWindow", series: Optional[DicomSeries], error: Optional[str]
) -> None:
    if not self._ui_batch_running:
        self._set_loading_state(False)
    self._loader = None
    self._loader_thread = None

    if error or series is None:
        message = error or "Failed to load DICOM."
        if self._ui_batch_running:
            self._log_ui_batch_result(False, message)
            self._ui_batch_index += 1
            QtCore.QTimer.singleShot(0, self._ui_batch_next)
            return
        self._show_error("Load Error", message)
        return

    self._apply_loaded_series(series)


def _apply_loaded_series(self: "MainWindow", series: DicomSeries) -> None:
    self._series = series
    self._current_path = series.metadata.path
    self._fps = series.metadata.fps or 30.0
    self._frame_index = 0
    self._frame_cache.clear()
    self._last_ai_result = None
    self._render_error_shown = False
    self._ui_batch_expect_render = self._ui_batch_running

    self._update_metadata_tabs(series)
    self._update_slider()
    self._render_frame()
    self._prefetch_around(self._frame_index, radius=self._prefetch_radius)
    self._update_status()


def _update_metadata_tabs(self: "MainWindow", series: DicomSeries) -> None:
    patient = asdict(series.patient)
    metadata = asdict(series.metadata)

    self._tab_patient.setPlainText("\n".join(f"{k}: {v}" for k, v in patient.items() if v))
    self._tab_series.setPlainText("\n".join(f"{k}: {v}" for k, v in metadata.items() if v))
    self._tab_technical.setPlainText(
        "\n".join(f"{k}: {v}" for k, v in metadata.get("additional", {}).items())
    )
    self._ai_table.setRowCount(0)
    self._ai_raw.setPlainText("")


def _update_slider(self: "MainWindow") -> None:
    if not self._series or self._series.frame_count == 0:
        self._slider.setMaximum(0)
        return
    total = self._series.frame_count
    self._slider.blockSignals(True)
    self._slider.setMinimum(0)
    self._slider.setMaximum(max(0, total - 1))
    self._slider.setValue(self._frame_index)
    self._slider.blockSignals(False)


def _render_frame(self: "MainWindow") -> None:
    if not self._series or self._series.frame_count == 0:
        message = "No frames available to render."
        self._viewer.set_empty(message)
        if self._ui_batch_running and self._ui_batch_expect_render:
            self._log_ui_batch_result(False, message)
            self._ui_batch_expect_render = False
            self._ui_batch_index += 1
            QtCore.QTimer.singleShot(0, self._ui_batch_next)
        return

    key = (str(self._current_path), self._frame_index)
    image = self._frame_cache.get(key)
    if image is None:
        try:
            frame = self._series.get_frame(self._frame_index)
        except Exception as exc:
            message = f"Failed to render frame {self._frame_index}: {exc}"
            self._viewer.set_empty(message)
            self._log_event(f"{message} ({self._current_path})")
            if self._ui_batch_running and self._ui_batch_expect_render:
                self._log_ui_batch_result(False, message)
                self._ui_batch_expect_render = False
                self._ui_batch_index += 1
                QtCore.QTimer.singleShot(0, self._ui_batch_next)
            if not self._render_error_shown:
                self._render_error_shown = True
                self._show_error("Render Error", message)
            return
        try:
            image = qimage_from_array(frame)
        except Exception as exc:
            message = f"Failed to convert frame {self._frame_index}: {exc}"
            self._viewer.set_empty(message)
            self._log_event(f"{message} ({self._current_path})")
            if self._ui_batch_running and self._ui_batch_expect_render:
                self._log_ui_batch_result(False, message)
                self._ui_batch_expect_render = False
                self._ui_batch_index += 1
                QtCore.QTimer.singleShot(0, self._ui_batch_next)
            if not self._render_error_shown:
                self._render_error_shown = True
                self._show_error("Render Error", message)
            return
        self._frame_cache.put(key, image)

    self._viewer.set_image(image)
    self._viewer.set_frame_info(self._frame_index, self._series.frame_count)
    if self._ui_batch_running and self._ui_batch_expect_render:
        self._log_ui_batch_result(True, "")
        self._ui_batch_expect_render = False
        self._ui_batch_index += 1
        QtCore.QTimer.singleShot(0, self._ui_batch_next)

    if self._last_ai_result:
        self._viewer.set_overlay_boxes(self._last_ai_result.boxes)
    else:
        self._viewer.clear_overlays()

    self._update_status()


def _prefetch_around(self: "MainWindow", index: int, radius: int = 2) -> None:
    if not self._prefetch_enabled:
        return
    if not self._series or self._series.frame_count == 0:
        return
    if radius <= 0:
        return

    max_index = self._series.frame_count - 1
    targets = [i for i in range(index - radius, index + radius + 1) if 0 <= i <= max_index]
    for i in targets:
        key = (str(self._current_path), i)
        if key in self._frame_cache:
            continue
        task = PrefetchTask(self._frame_cache, key, self._series.get_frame, i)
        self._prefetch_pool.start(task)


def _slider_changed(self: "MainWindow", value: int) -> None:
    if not self._series or self._series.frame_count == 0:
        return
    self._frame_index = max(0, min(value, self._series.frame_count - 1))
    self._render_frame()
    self._prefetch_around(self._frame_index, radius=self._prefetch_radius)


def _prev_frame(self: "MainWindow") -> None:
    if not self._series or self._series.frame_count == 0:
        return
    self._frame_index = (self._frame_index - 1) % self._series.frame_count
    self._slider.setValue(self._frame_index)


def _next_frame(self: "MainWindow") -> None:
    if not self._series or self._series.frame_count == 0:
        return
    self._frame_index = (self._frame_index + 1) % self._series.frame_count
    self._slider.setValue(self._frame_index)


def _toggle_play(self: "MainWindow") -> None:
    if not self._series or self._series.frame_count == 0:
        return
    self._playing = not self._playing
    self._btn_play.setText("Pause" if self._playing else "Play")
    self._btn_play.setIcon(self._icon("pause" if self._playing else "play"))
    if self._playing:
        interval_ms = max(1, int(1000 / self._fps))
        self._timer.start(interval_ms)
    else:
        self._timer.stop()


def _tick(self: "MainWindow") -> None:
    if not self._playing:
        return
    self._next_frame()
