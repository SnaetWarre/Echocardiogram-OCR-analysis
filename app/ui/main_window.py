from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.io.dicom_loader import load_dicom_series
from app.io.errors import DicomLoadError
from app.models.types import AiResult, DicomSeries
from app.ui.components.controls import ControlsWidget
from app.ui.components.metadata_tabs import MetadataTabsWidget
from app.ui.components.sidebar import SidebarWidget
from app.ui.state import ViewerState
from app.ui.theme import apply_theme
from app.ui.widgets.image_viewer import ImageViewer
from app.ui.workers import AiRunWorker, BatchTestWorker, DicomLoadWorker, PrefetchTask
from app.utils.cache import LruFrameCache


class MainWindow(QtWidgets.QMainWindow):
    """The main application window for the DICOM viewer."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DICOM Cine Viewer")
        self.resize(1400, 900)

        # 1. Initialize State
        self._state = ViewerState(self)

        # Caches and Workers
        self._frame_cache = LruFrameCache[tuple[str, int]](capacity=256)
        self._prefetch_pool = QtCore.QThreadPool.globalInstance()
        if self._state.prefetch_threads > 0:
            self._prefetch_pool.setMaxThreadCount(self._state.prefetch_threads)

        self._loader_thread: QtCore.QThread | None = None
        self._loader: DicomLoadWorker | None = None
        self._ai_thread: QtCore.QThread | None = None
        self._ai_worker: AiRunWorker | None = None
        self._batch_thread: QtCore.QThread | None = None
        self._batch_worker: BatchTestWorker | None = None

        # Logs & Error state
        self._log_dir = Path.cwd() / "logs"
        self._log_file = self._log_dir / "dicom_viewer.log"
        self._suppress_error_dialogs = os.getenv("DICOM_SUPPRESS_ERRORS", "0") == "1"
        self._max_error_dialogs = int(os.getenv("DICOM_MAX_ERROR_DIALOGS", "3"))
        self._error_dialog_count = 0
        self._render_error_shown = False

        # Timer for playback
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

        # 2. Build UI Hierarchy
        self._build_ui()
        self._apply_theme()

        # Connect Top-Level Signals
        self._state.series_loaded.connect(self._on_series_loaded)
        self._state.frame_changed.connect(self._on_frame_changed)
        self._state.play_state_changed.connect(self._on_play_state_changed)
        self._state.ai_result_ready.connect(self._on_ai_result_ready)
        self._state.error_occurred.connect(self._show_error)
        self._state.loading_state_changed.connect(self._on_loading_state_changed)

        self._update_status()

    def _apply_theme(self) -> None:
        apply_theme(self)

    def _icon(self, name: str) -> QtGui.QIcon:
        base = Path(__file__).resolve().parent / "icons"
        path = base / f"{name}.svg"
        if path.exists():
            return QtGui.QIcon(str(path))
        return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Splitter to manage left/right sizes
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left: Sidebar
        self._sidebar = SidebarWidget(self._state)
        self._sidebar.file_selected.connect(self._load_dicom)
        splitter.addWidget(self._sidebar)

        # Right: Main content area
        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_header = QtWidgets.QHBoxLayout()
        right_header.addStretch(1)
        self._btn_toggle_sidebar = QtWidgets.QToolButton()
        self._btn_toggle_sidebar.setText("Collapse Sidebar")
        self._btn_toggle_sidebar.setIcon(self._icon("sidebar_collapse"))
        self._btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)
        right_header.addWidget(self._btn_toggle_sidebar)
        right_layout.addLayout(right_header)

        self._viewer = ImageViewer()
        self._viewer.viewChanged.connect(self._on_view_changed)
        right_layout.addWidget(self._viewer, stretch=1)

        self._build_toolbar()

        # Controls & Tabs
        self._controls = ControlsWidget(self._state)
        right_layout.addWidget(self._controls)

        self._tabs = MetadataTabsWidget(self._state)
        right_layout.addWidget(self._tabs)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        # Status Bar
        self._status = QtWidgets.QStatusBar()
        self.setStatusBar(self._status)
        self._status_file = QtWidgets.QLabel("No file")
        self._status_frame = QtWidgets.QLabel("Frame 0/0")
        self._status_fps = QtWidgets.QLabel("FPS 0")
        self._status_cache = QtWidgets.QLabel("Cache 0/0")
        self._status.addWidget(self._status_file, 1)
        self._status.addWidget(self._status_frame)
        self._status.addWidget(self._status_fps)
        self._status.addWidget(self._status_cache)

    def _build_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(18, 18))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        act_open = QtGui.QAction(self._icon("open_file"), "Open File", self)
        act_folder = QtGui.QAction(self._icon("open_folder"), "Open Folder", self)
        act_toggle = QtGui.QAction(self._icon("sidebar_collapse"), "Toggle Sidebar", self)
        act_zoom_in = QtGui.QAction(self._icon("zoom_in"), "Zoom In", self)
        act_zoom_out = QtGui.QAction(self._icon("zoom_out"), "Zoom Out", self)
        act_zoom_fit = QtGui.QAction(self._icon("zoom_fit"), "Zoom to Fit", self)

        self._act_toggle_sidebar = act_toggle

        act_open.triggered.connect(self._sidebar._open_file_dialog)
        act_folder.triggered.connect(self._sidebar._open_folder_dialog)
        act_toggle.triggered.connect(self._toggle_sidebar)
        act_zoom_in.triggered.connect(lambda: self._viewer.zoom(1.2))
        act_zoom_out.triggered.connect(lambda: self._viewer.zoom(1 / 1.2))
        act_zoom_fit.triggered.connect(self._viewer.zoom_to_fit)

        toolbar.addAction(act_open)
        toolbar.addAction(act_folder)
        toolbar.addSeparator()
        toolbar.addAction(act_toggle)
        toolbar.addSeparator()
        toolbar.addAction(act_zoom_in)
        toolbar.addAction(act_zoom_out)
        toolbar.addAction(act_zoom_fit)
        toolbar.addSeparator()

        if getattr(self._state, "ai_enabled", False):
            act_run_ai = QtGui.QAction(self._icon("ai_run"), "Run AI", self)
            act_run_ai.triggered.connect(self._run_ai)
            toolbar.addAction(act_run_ai)

    def _log_event(self, message: str) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def _show_error(self, title: str, message: str) -> None:
        if self._suppress_error_dialogs:
            return
        if self._error_dialog_count >= self._max_error_dialogs:
            return
        self._error_dialog_count += 1
        QtWidgets.QMessageBox.critical(self, title, message)

    def _toggle_sidebar(self) -> None:
        self._sidebar.toggle_collapsed()
        collapsed = self._sidebar.is_collapsed()
        if collapsed:
            self._btn_toggle_sidebar.setText("Expand Sidebar")
            self._btn_toggle_sidebar.setIcon(self._icon("sidebar_expand"))
            if hasattr(self, "_act_toggle_sidebar"):
                self._act_toggle_sidebar.setText("Expand Sidebar")
                self._act_toggle_sidebar.setIcon(self._icon("sidebar_expand"))
        else:
            self._btn_toggle_sidebar.setText("Collapse Sidebar")
            self._btn_toggle_sidebar.setIcon(self._icon("sidebar_collapse"))
            if hasattr(self, "_act_toggle_sidebar"):
                self._act_toggle_sidebar.setText("Collapse Sidebar")
                self._act_toggle_sidebar.setIcon(self._icon("sidebar_collapse"))

    def _update_status(self) -> None:
        path = self._state.current_path
        name = path.name if path else "No file"
        self._status_file.setText(name)

        series = self._state.series
        total = series.frame_count if series else 0
        frame_text = f"Frame {self._state.frame_index + 1}/{total}" if total else "Frame 0/0"
        self._status_frame.setText(frame_text)
        self._status_fps.setText(f"FPS {self._state.fps:.2f}")

        stats = self._frame_cache.stats()
        self._status_cache.setText(f"Cache {stats.size}/{stats.capacity}")

    def _on_view_changed(self, zoom: float) -> None:
        _ = zoom
        self._update_status()

    # --- Loading Logic ---
    def _on_loading_state_changed(self, loading: bool, message: str) -> None:
        if message:
            self.statusBar().showMessage(message)
        if loading:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _load_dicom(self, path: Path) -> None:
        if not path.exists():
            self.statusBar().showMessage(f"File not found: {path}", 3000)
            return

        self._log_event(f"Load request: {path}")
        if self._state.load_on_main_thread:
            self._state.set_loading(True, f"Loading {path.name}...")
            try:
                series = load_dicom_series(path, load_pixels=not self._state.lazy_decode_enabled)
            except DicomLoadError as exc:
                self._log_event(f"Load failed (main thread): {path} :: {exc}")
                self._state.set_loading(False)
                self._state.report_error("Load Error", str(exc))
                return
            except Exception as exc:
                self._log_event(f"Load failed (unexpected): {path} :: {exc}")
                self._state.set_loading(False)
                self._state.report_error(
                    "Load Error", f"Unexpected error while loading file: {exc}"
                )
                return
            self._state.set_loading(False)
            self._log_event(f"Load finished (main thread): {path}")
            self._state.set_series(series)
            return

        if self._loader_thread and self._loader_thread.isRunning():
            self.statusBar().showMessage("Already loading a DICOM file.", 2000)
            return

        self._state.set_loading(True, f"Loading {path.name}...")
        self._loader_thread = QtCore.QThread(self)
        self._loader = DicomLoadWorker(path, load_pixels=not self._state.lazy_decode_enabled)
        self._loader.moveToThread(self._loader_thread)
        self._loader_thread.started.connect(self._loader.run)
        self._loader.finished.connect(self._on_load_finished)
        self._loader.finished.connect(self._loader_thread.quit)
        self._loader.finished.connect(self._loader.deleteLater)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)
        self._loader_thread.start()

    def _on_load_finished(self, series: DicomSeries | None, error: str | None) -> None:
        self._state.set_loading(False)
        self._loader = None
        self._loader_thread = None

        if error or series is None:
            message = error or "Failed to load DICOM."
            self._log_event(f"Load failed (worker): {message}")
            self._state.report_error("Load Error", message)
            return

        self._log_event(f"Load finished (worker): {series.metadata.path}")
        self._state.set_series(series)

    # --- Render & Playback State Handlers ---
    def _on_series_loaded(self, series: DicomSeries) -> None:
        self._frame_cache.clear()
        self._render_error_shown = False
        self._render_frame()
        self._prefetch_around(self._state.frame_index, radius=self._state.prefetch_radius)
        self._update_status()

    def _on_frame_changed(self, frame_index: int) -> None:
        self._render_frame()
        self._prefetch_around(frame_index, radius=self._state.prefetch_radius)

    def _on_play_state_changed(self, playing: bool) -> None:
        if playing:
            interval_ms = max(1, int(1000 / self._state.fps))
            self._timer.start(interval_ms)
        else:
            self._timer.stop()

    def _tick(self) -> None:
        if not self._state.playing:
            return
        self._state.next_frame()

    # --- AI Logic ---
    def _on_ai_result_ready(self, result: AiResult) -> None:
        self._viewer.set_overlay_boxes(result.boxes)

    def _run_ai(self) -> None:
        if not self._state.ai_enabled or self._state.pipeline_manager is None:
            QtWidgets.QMessageBox.information(
                self, "AI Disabled", "AI pipeline is not enabled in environment."
            )
            return
        path = self._state.current_path
        if not path:
            return

        if self._ai_thread and self._ai_thread.isRunning():
            self.statusBar().showMessage("AI is already running.", 2000)
            return

        self._state.set_loading(True, "Running AI inference...")
        self._log_event(f"Starting AI run on: {path}")

        self._ai_thread = QtCore.QThread(self)
        self._ai_worker = AiRunWorker(self._state.pipeline_manager, path)
        self._ai_worker.moveToThread(self._ai_thread)
        self._ai_thread.started.connect(self._ai_worker.run)
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.finished.connect(self._ai_worker.deleteLater)
        self._ai_thread.finished.connect(self._ai_thread.deleteLater)
        self._ai_thread.start()

    def _on_ai_finished(self, result: AiResult | None, error: str | None) -> None:
        self._state.set_loading(False)
        self._ai_worker = None
        self._ai_thread = None

        if error or result is None:
            message = error or "Failed to run AI."
            self._log_event(f"AI failed: {message}")
            self._state.report_error("AI Error", message)
            return

        self._log_event(f"AI completed with {len(result.measurements)} measurements.")
        self._state.apply_ai_result(result)

    # --- Frame Handling ---
    def _render_frame(self) -> None:
        series = self._state.series
        path = self._state.current_path
        index = self._state.frame_index

        if not series or series.frame_count == 0 or not path:
            self._viewer.set_empty("No frames available to render.")
            return

        from app.utils.image import qimage_from_array

        key = (str(path), index)
        image = self._frame_cache.get(key)
        if image is None:
            try:
                frame = series.get_frame(index)
                image = qimage_from_array(frame)
            except Exception as exc:
                message = f"Failed to render frame {index}: {exc}"
                self._viewer.set_empty(message)
                self._log_event(f"{message} ({path})")
                if not self._render_error_shown:
                    self._render_error_shown = True
                    self._state.report_error("Render Error", message)
                return
            self._frame_cache.put(key, image)

        self._viewer.set_image(image)
        self._viewer.set_frame_info(index, series.frame_count)

        if self._state.last_ai_result:
            self._viewer.set_overlay_boxes(self._state.last_ai_result.boxes)
        else:
            self._viewer.clear_overlays()

        self._update_status()

    def _prefetch_around(self, index: int, radius: int = 2) -> None:
        if not self._state.prefetch_enabled:
            return
        series = self._state.series
        path = self._state.current_path
        if not series or series.frame_count == 0 or not path:
            return
        if radius <= 0:
            return

        max_index = series.frame_count - 1
        targets = [i for i in range(index - radius, index + radius + 1) if 0 <= i <= max_index]
        for i in targets:
            key = (str(path), i)
            if key in self._frame_cache:
                continue
            task = PrefetchTask(self._frame_cache, key, series.get_frame, i)
            self._prefetch_pool.start(task)
