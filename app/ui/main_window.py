from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PySide6 import QtCore, QtWidgets

from app.models.types import AiResult, DicomSeries
from app.pipeline.ai_pipeline import build_default_manager
from app.ui.main_window_ai import (
    _apply_ai_result,
    _export_ai_csv,
    _export_ai_txt,
    _on_ai_failed,
    _on_ai_finished,
    _run_ai,
)
from app.ui.main_window_batch import (
    _finish_ui_batch,
    _log_event,
    _log_ui_batch_result,
    _on_batch_finished,
    _on_batch_progress,
    _show_error,
    _start_batch_test,
    _start_ui_batch_run,
    _ui_batch_next,
)
from app.ui.main_window_ui import _build_toolbar, _build_ui, _icon
from app.ui.main_window_view import (
    _apply_loaded_series,
    _load_dicom,
    _next_frame,
    _on_filter_changed,
    _on_load_finished,
    _on_search_changed,
    _on_view_changed,
    _open_file,
    _open_folder,
    _prefetch_around,
    _prev_frame,
    _render_frame,
    _set_loading_state,
    _set_sidebar_collapsed,
    _set_tree_root,
    _slider_changed,
    _tick,
    _toggle_filter,
    _toggle_play,
    _toggle_sidebar,
    _tree_double_clicked,
    _update_metadata_tabs,
    _update_slider,
    _update_status,
)
from app.ui.theme import apply_theme
from app.ui.workers import AiRunWorker, BatchTestWorker, DicomLoadWorker
from app.utils.cache import LruFrameCache


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DICOM Cine Viewer")
        self.resize(1400, 900)

        self._series: Optional[DicomSeries] = None
        self._current_path: Optional[Path] = None
        self._frame_index = 0
        self._fps = 30.0
        self._playing = False
        self._sidebar_collapsed = False
        self._lazy_decode_enabled = os.getenv("DICOM_LAZY_DECODE", "1") == "1"
        self._load_on_main_thread = os.getenv("DICOM_LOAD_MAIN_THREAD", "0") == "1"
        self._prefetch_enabled = os.getenv("DICOM_PREFETCH", "0") == "1"
        self._prefetch_radius = int(os.getenv("DICOM_PREFETCH_RADIUS", "0"))
        self._prefetch_threads = int(os.getenv("DICOM_PREFETCH_THREADS", "1"))

        self._frame_cache = LruFrameCache[Tuple[str, int]](capacity=256)
        self._prefetch_pool = QtCore.QThreadPool.globalInstance()
        if self._prefetch_threads > 0:
            self._prefetch_pool.setMaxThreadCount(self._prefetch_threads)

        self._pipeline_manager = build_default_manager()
        self._last_ai_result: Optional[AiResult] = None

        self._loader_thread: Optional[QtCore.QThread] = None
        self._loader: Optional[DicomLoadWorker] = None
        self._ai_thread: Optional[QtCore.QThread] = None
        self._ai_worker: Optional[AiRunWorker] = None
        self._batch_thread: Optional[QtCore.QThread] = None
        self._batch_worker: Optional[BatchTestWorker] = None
        self._log_dir = Path.cwd() / "logs"
        self._log_file = self._log_dir / "dicom_viewer.log"
        self._batch_log_file: Optional[Path] = None
        self._ui_batch_log_file: Optional[Path] = None
        self._ui_batch_paths: list[Path] = []
        self._ui_batch_index = 0
        self._ui_batch_running = False
        self._ui_batch_start_time = 0.0
        self._ui_batch_item_start = 0.0
        self._ui_batch_current_path: Optional[Path] = None
        self._ui_batch_expect_render = False
        self._ui_batch_ok = 0
        self._ui_batch_fail = 0
        self._suppress_error_dialogs = os.getenv("DICOM_SUPPRESS_ERRORS", "0") == "1"
        self._max_error_dialogs = int(os.getenv("DICOM_MAX_ERROR_DIALOGS", "3"))
        self._error_dialog_count = 0
        self._render_error_shown = False

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._apply_theme()
        self._update_status()

    def _apply_theme(self) -> None:
        apply_theme(self)


MainWindow._build_ui = _build_ui
MainWindow._icon = _icon
MainWindow._build_toolbar = _build_toolbar

MainWindow._show_error = _show_error
MainWindow._log_event = _log_event
MainWindow._start_ui_batch_run = _start_ui_batch_run
MainWindow._ui_batch_next = _ui_batch_next
MainWindow._log_ui_batch_result = _log_ui_batch_result
MainWindow._finish_ui_batch = _finish_ui_batch
MainWindow._start_batch_test = _start_batch_test
MainWindow._on_batch_progress = _on_batch_progress
MainWindow._on_batch_finished = _on_batch_finished

MainWindow._update_status = _update_status
MainWindow._on_view_changed = _on_view_changed
MainWindow._on_search_changed = _on_search_changed
MainWindow._on_filter_changed = _on_filter_changed
MainWindow._toggle_filter = _toggle_filter
MainWindow._open_folder = _open_folder
MainWindow._open_file = _open_file
MainWindow._set_tree_root = _set_tree_root
MainWindow._tree_double_clicked = _tree_double_clicked
MainWindow._toggle_sidebar = _toggle_sidebar
MainWindow._set_sidebar_collapsed = _set_sidebar_collapsed
MainWindow._set_loading_state = _set_loading_state
MainWindow._load_dicom = _load_dicom
MainWindow._on_load_finished = _on_load_finished
MainWindow._apply_loaded_series = _apply_loaded_series
MainWindow._update_metadata_tabs = _update_metadata_tabs
MainWindow._update_slider = _update_slider
MainWindow._render_frame = _render_frame
MainWindow._prefetch_around = _prefetch_around
MainWindow._slider_changed = _slider_changed
MainWindow._prev_frame = _prev_frame
MainWindow._next_frame = _next_frame
MainWindow._toggle_play = _toggle_play
MainWindow._tick = _tick

MainWindow._run_ai = _run_ai
MainWindow._on_ai_finished = _on_ai_finished
MainWindow._on_ai_failed = _on_ai_failed
MainWindow._apply_ai_result = _apply_ai_result
MainWindow._export_ai_csv = _export_ai_csv
MainWindow._export_ai_txt = _export_ai_txt
