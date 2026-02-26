from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PySide6 import QtCore, QtWidgets

from app.models.types import AiResult, DicomSeries
from app.pipeline.ai_pipeline import build_default_manager
from app.ui.main_window_ai import MainWindowAIMixin
from app.ui.main_window_batch import MainWindowBatchMixin
from app.ui.main_window_ui import MainWindowUIMixin
from app.ui.main_window_view import MainWindowViewMixin
from app.ui.theme import apply_theme
from app.ui.workers import AiRunWorker, BatchTestWorker, DicomLoadWorker
from app.utils.cache import LruFrameCache


class MainWindow(MainWindowUIMixin, MainWindowViewMixin, MainWindowAIMixin, MainWindowBatchMixin, QtWidgets.QMainWindow):
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
        # Stability-first default: threaded loading can be re-enabled explicitly.
        self._load_on_main_thread = os.getenv("DICOM_LOAD_MAIN_THREAD", "1") == "1"
        self._prefetch_enabled = os.getenv("DICOM_PREFETCH", "0") == "1"
        self._prefetch_radius = int(os.getenv("DICOM_PREFETCH_RADIUS", "0"))
        self._prefetch_threads = int(os.getenv("DICOM_PREFETCH_THREADS", "1"))
        self._ai_enabled = os.getenv("DICOM_AI_ENABLED", "0") == "1"

        self._frame_cache = LruFrameCache[Tuple[str, int]](capacity=256)
        self._prefetch_pool = QtCore.QThreadPool.globalInstance()
        if self._prefetch_threads > 0:
            self._prefetch_pool.setMaxThreadCount(self._prefetch_threads)

        self._pipeline_manager = build_default_manager() if self._ai_enabled else None
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
