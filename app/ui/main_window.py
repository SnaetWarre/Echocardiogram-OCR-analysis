from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.io.dicom_loader import DicomLoadError, load_dicom_series
from app.models.types import AiResult, DicomSeries, PipelineRequest
from app.pipeline.ai_pipeline import PipelineManager, build_default_manager
from app.ui.widgets.image_viewer import ImageViewer
from app.utils.cache import LruFrameCache
from app.utils.image import qimage_from_array


class FileFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._search_text = ""
        self._show_dcm_only = True

    def set_search_text(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def set_show_dcm_only(self, value: bool) -> None:
        self._show_dcm_only = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True

        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        path = Path(model.filePath(index))
        if path.is_dir():
            return True

        if self._show_dcm_only and path.suffix.lower() != ".dcm":
            return False

        if self._search_text and self._search_text not in path.name.lower():
            return False

        return True


class DicomLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(object, object)  # (DicomSeries|None, error|None)

    def __init__(self, path: Path, load_pixels: bool = True) -> None:
        super().__init__()
        self._path = path
        self._load_pixels = load_pixels

    @QtCore.Slot()
    def run(self) -> None:
        try:
            series = load_dicom_series(self._path, load_pixels=self._load_pixels)
        except DicomLoadError as exc:
            self.finished.emit(None, str(exc))
            return
        except Exception as exc:
            self.finished.emit(None, f"Failed to load DICOM: {exc}")
            return
        self.finished.emit(series, None)


class AiRunWorker(QtCore.QObject):
    finished = QtCore.Signal(object)  # PipelineResult

    def __init__(self, manager: PipelineManager, request: PipelineRequest) -> None:
        super().__init__()
        self._manager = manager
        self._request = request

    @QtCore.Slot()
    def run(self) -> None:
        result = self._manager.run(self._request)
        self.finished.emit(result)


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

        self._frame_cache = LruFrameCache[Tuple[str, int]](capacity=256)
        self._prefetch_pool = QtCore.QThreadPool.globalInstance()

        self._pipeline_manager = build_default_manager()
        self._last_ai_result: Optional[AiResult] = None

        self._loader_thread: Optional[QtCore.QThread] = None
        self._loader: Optional[DicomLoadWorker] = None
        self._ai_thread: Optional[QtCore.QThread] = None
        self._ai_worker: Optional[AiRunWorker] = None

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._apply_theme()
        self._update_status()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self._left_panel = QtWidgets.QFrame()
        self._left_panel.setObjectName("leftPanel")
        self._left_panel.setMinimumWidth(260)

        self._left_stack = QtWidgets.QStackedWidget()
        left_panel_layout = QtWidgets.QVBoxLayout(self._left_panel)
        left_panel_layout.setContentsMargins(8, 8, 8, 8)
        left_panel_layout.addWidget(self._left_stack)

        self._left_full = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self._left_full)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search DICOM files...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self._search)

        self._filter_toggle = QtWidgets.QCheckBox("Show only .dcm")
        self._filter_toggle.setChecked(True)
        self._filter_toggle.stateChanged.connect(self._on_filter_changed)
        left_layout.addWidget(self._filter_toggle)

        self._fs_model = QtWidgets.QFileSystemModel()
        self._fs_model.setFilter(
            QtCore.QDir.AllEntries | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs
        )
        self._fs_model.setRootPath(str(Path.cwd()))

        self._proxy_model = FileFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._fs_model)

        self._tree = QtWidgets.QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._tree.doubleClicked.connect(self._tree_double_clicked)
        self._tree.setModel(self._proxy_model)
        self._tree.setRootIndex(self._proxy_model.mapFromSource(self._fs_model.index(str(Path.cwd()))))
        left_layout.addWidget(self._tree)

        self._sidebar_slim = QtWidgets.QWidget()
        self._sidebar_slim.setObjectName("sidebarSlim")
        slim_layout = QtWidgets.QVBoxLayout(self._sidebar_slim)
        slim_layout.setContentsMargins(0, 0, 0, 0)
        slim_layout.setSpacing(8)

        self._btn_slim_expand = QtWidgets.QToolButton()
        self._btn_slim_expand.setIcon(self._icon("sidebar_expand"))
        self._btn_slim_expand.setToolTip("Expand Sidebar")
        self._btn_slim_expand.clicked.connect(lambda: self._set_sidebar_collapsed(False))
        slim_layout.addWidget(self._btn_slim_expand)

        self._btn_slim_open_file = QtWidgets.QToolButton()
        self._btn_slim_open_file.setIcon(self._icon("open_file"))
        self._btn_slim_open_file.setToolTip("Open File")
        self._btn_slim_open_file.clicked.connect(self._open_file)
        slim_layout.addWidget(self._btn_slim_open_file)

        self._btn_slim_open_folder = QtWidgets.QToolButton()
        self._btn_slim_open_folder.setIcon(self._icon("open_folder"))
        self._btn_slim_open_folder.setToolTip("Open Folder")
        self._btn_slim_open_folder.clicked.connect(self._open_folder)
        slim_layout.addWidget(self._btn_slim_open_folder)

        self._btn_slim_filter = QtWidgets.QToolButton()
        self._btn_slim_filter.setIcon(self._icon("filter"))
        self._btn_slim_filter.setToolTip("Toggle .dcm Filter")
        self._btn_slim_filter.setCheckable(True)
        self._btn_slim_filter.setChecked(self._filter_toggle.isChecked())
        self._btn_slim_filter.clicked.connect(self._toggle_filter)
        slim_layout.addWidget(self._btn_slim_filter)

        slim_layout.addStretch(1)

        self._left_stack.addWidget(self._left_full)
        self._left_stack.addWidget(self._sidebar_slim)

        right_container = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_header = QtWidgets.QHBoxLayout()
        right_header.addStretch(1)
        self._btn_toggle_sidebar = QtWidgets.QToolButton()
        self._btn_toggle_sidebar.setText("Collapse Sidebar")
        self._btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)
        right_header.addWidget(self._btn_toggle_sidebar)
        right_layout.addLayout(right_header)

        self._viewer = ImageViewer()
        self._viewer.viewChanged.connect(self._on_view_changed)
        right_layout.addWidget(self._viewer, stretch=1)

        self._build_toolbar()

        controls = QtWidgets.QFrame()
        controls.setObjectName("controls")
        controls_layout = QtWidgets.QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 8, 12, 8)
        controls_layout.setSpacing(12)

        self._btn_prev = QtWidgets.QPushButton("Prev")
        self._btn_prev.setIcon(self._icon("prev"))
        self._btn_prev.setIconSize(QtCore.QSize(16, 16))
        self._btn_prev.setToolTip("Previous frame")
        self._btn_play = QtWidgets.QPushButton("Play")
        self._btn_play.setIcon(self._icon("play"))
        self._btn_play.setIconSize(QtCore.QSize(16, 16))
        self._btn_play.setToolTip("Play / Pause")
        self._btn_next = QtWidgets.QPushButton("Next")
        self._btn_next.setIcon(self._icon("next"))
        self._btn_next.setIconSize(QtCore.QSize(16, 16))
        self._btn_next.setToolTip("Next frame")
        self._btn_prev.clicked.connect(self._prev_frame)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_next.clicked.connect(self._next_frame)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._slider_changed)

        self._frame_label = QtWidgets.QLabel("Frame 0/0")
        self._frame_label.setMinimumWidth(90)
        self._frame_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        controls_layout.addWidget(self._btn_prev)
        controls_layout.addWidget(self._btn_play)
        controls_layout.addWidget(self._btn_next)
        controls_layout.addWidget(self._slider, stretch=1)
        controls_layout.addWidget(self._frame_label)

        right_layout.addWidget(controls)

        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setObjectName("metadataTabs")

        self._tab_patient = QtWidgets.QTextEdit()
        self._tab_patient.setReadOnly(True)
        self._tabs.addTab(self._tab_patient, "Patient")

        self._tab_series = QtWidgets.QTextEdit()
        self._tab_series.setReadOnly(True)
        self._tabs.addTab(self._tab_series, "Series")

        self._tab_technical = QtWidgets.QTextEdit()
        self._tab_technical.setReadOnly(True)
        self._tabs.addTab(self._tab_technical, "Technical")

        self._tab_ai = QtWidgets.QWidget()
        self._tab_ai_layout = QtWidgets.QVBoxLayout(self._tab_ai)
        self._tab_ai_layout.setContentsMargins(8, 8, 8, 8)
        self._tab_ai_layout.setSpacing(8)

        self._ai_table = QtWidgets.QTableWidget(0, 3)
        self._ai_table.setHorizontalHeaderLabels(["Measurement", "Value", "Unit"])
        self._ai_table.horizontalHeader().setStretchLastSection(True)
        self._ai_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
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

        self._tabs.addTab(self._tab_ai, "AI Results")
        right_layout.addWidget(self._tabs)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self._left_panel)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)

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

        self._set_sidebar_collapsed(False)

    def _icon(self, name: str) -> QtGui.QIcon:
        base = Path(__file__).resolve().parent / "icons"
        path = base / f"{name}.svg"
        if path.exists():
            return QtGui.QIcon(str(path))
        return self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)

    def _build_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(18, 18))
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        act_open = QtGui.QAction(self._icon("open_file"), "Open File", self)
        act_folder = QtGui.QAction(self._icon("open_folder"), "Open Folder", self)
        act_toggle = QtGui.QAction(self._icon("sidebar_collapse"), "Toggle Sidebar", self)
        act_filter = QtGui.QAction(self._icon("filter"), "Toggle .dcm Filter", self)
        act_filter.setCheckable(True)
        act_filter.setChecked(self._filter_toggle.isChecked())
        act_run_ai = QtGui.QAction(self._icon("ai_run"), "Run AI", self)
        act_zoom_in = QtGui.QAction(self._icon("zoom_in"), "Zoom In", self)
        act_zoom_out = QtGui.QAction(self._icon("zoom_out"), "Zoom Out", self)
        act_zoom_fit = QtGui.QAction(self._icon("zoom_fit"), "Zoom to Fit", self)

        self._act_toggle_sidebar = act_toggle
        self._act_filter = act_filter

        act_open.triggered.connect(self._open_file)
        act_folder.triggered.connect(self._open_folder)
        act_toggle.triggered.connect(self._toggle_sidebar)
        act_filter.triggered.connect(self._toggle_filter)
        act_run_ai.triggered.connect(self._run_ai)
        act_zoom_in.triggered.connect(lambda: self._viewer.zoom(1.2))
        act_zoom_out.triggered.connect(lambda: self._viewer.zoom(1 / 1.2))
        act_zoom_fit.triggered.connect(self._viewer.zoom_to_fit)

        toolbar.addAction(act_open)
        toolbar.addAction(act_folder)
        toolbar.addSeparator()
        toolbar.addAction(act_toggle)
        toolbar.addAction(act_filter)
        toolbar.addSeparator()
        toolbar.addAction(act_zoom_in)
        toolbar.addAction(act_zoom_out)
        toolbar.addAction(act_zoom_fit)
        toolbar.addSeparator()
        toolbar.addAction(act_run_ai)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #F5F7FA;
            }
            #leftPanel {
                background: #F0F3F7;
                border: 1px solid #C9D1DA;
                border-radius: 3px;
            }
            #controls {
                background: #F0F3F7;
                border: 1px solid #C9D1DA;
                border-radius: 3px;
            }
            #metadataTabs {
                background: #FFFFFF;
                border: 1px solid #C9D1DA;
                border-radius: 3px;
            }
            QToolBar {
                background: #E9EDF2;
                border: none;
                border-bottom: 1px solid #C9D1DA;
                spacing: 6px;
                padding: 4px;
            }
            QToolBar QToolButton {
                background: transparent;
                color: #2B3A46;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 4px 6px;
            }
            QToolBar QToolButton:hover {
                background: #DDE4EC;
                border: 1px solid #C9D1DA;
            }
            QToolBar QToolButton:pressed {
                background: #CFD8E3;
            }
            #sidebarSlim QToolButton {
                background: #E7EBF1;
                color: #2B3A46;
                border: 1px solid #C9D1DA;
                border-radius: 2px;
                padding: 6px;
            }
            #sidebarSlim QToolButton:hover {
                background: #DDE4EC;
            }
            #sidebarSlim QToolButton:pressed {
                background: #CFD8E3;
            }
            QPushButton, QToolButton {
                background: #EEF2F6;
                color: #2B3A46;
                border: 1px solid #C9D1DA;
                border-radius: 3px;
                padding: 6px 10px;
            }
            QPushButton:hover, QToolButton:hover {
                background: #E1E7EF;
            }
            QPushButton:pressed, QToolButton:pressed {
                background: #D5DEE8;
            }
            QPushButton:disabled, QToolButton:disabled {
                background: #F4F6F9;
                color: #8A96A3;
                border-color: #D3DAE2;
            }
            QTabWidget::pane {
                border: 1px solid #C9D1DA;
                border-radius: 3px;
                background: #FFFFFF;
            }
            QTabBar::tab {
                background: #EEF2F6;
                border: 1px solid #C9D1DA;
                border-bottom: none;
                padding: 6px 12px;
                margin-right: 4px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                color: #2B3A46;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
            }
            QHeaderView::section {
                background: #EEF2F6;
                color: #2B3A46;
                border: 1px solid #C9D1DA;
                padding: 4px 6px;
            }
            QTableWidget {
                background: #FFFFFF;
                gridline-color: #E1E6ED;
                border: 1px solid #C9D1DA;
                border-radius: 2px;
            }
            QStatusBar {
                background: #E9EDF2;
                color: #2B3A46;
                border-top: 1px solid #C9D1DA;
            }
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #C9D1DA;
                border-radius: 2px;
                padding: 6px 8px;
            }
            QCheckBox {
                color: #3A4756;
            }
            QTreeView {
                background: #FFFFFF;
                alternate-background-color: #F4F6F9;
                color: #2A3642;
                border: 1px solid #C9D1DA;
                border-radius: 2px;
                selection-background-color: #DCE5F0;
                selection-color: #1B2430;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #C9D1DA;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                background: #A5B0BE;
                margin: -4px 0;
                border-radius: 2px;
            }
            QLabel {
                color: #2A3642;
            }
            QTextEdit {
                background: #FFFFFF;
                color: #2A3642;
                border: 1px solid #C9D1DA;
                border-radius: 2px;
                font-family: "Segoe UI", "Inter", "Arial", sans-serif;
                font-size: 11px;
            }
            """
        )

    def _update_status(self) -> None:
        name = self._current_path.name if self._current_path else "No file"
        self._status_file.setText(name)
        total = self._series.frame_count if self._series else 0
        self._status_frame.setText(f"Frame {self._frame_index + 1}/{total}" if total else "Frame 0/0")
        self._status_fps.setText(f"FPS {self._fps:.2f}")
        stats = self._frame_cache.stats()
        self._status_cache.setText(f"Cache {stats.size}/{stats.capacity}")

    def _on_view_changed(self, zoom: float) -> None:
        self._update_status()

    def _on_search_changed(self, text: str) -> None:
        self._proxy_model.set_search_text(text)

    def _on_filter_changed(self) -> None:
        checked = self._filter_toggle.isChecked()
        self._proxy_model.set_show_dcm_only(checked)
        self._btn_slim_filter.blockSignals(True)
        self._btn_slim_filter.setChecked(checked)
        self._btn_slim_filter.blockSignals(False)
        if hasattr(self, "_act_filter"):
            self._act_filter.blockSignals(True)
            self._act_filter.setChecked(checked)
            self._act_filter.blockSignals(False)

    def _toggle_filter(self) -> None:
        self._filter_toggle.setChecked(not self._filter_toggle.isChecked())

    def _open_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder", str(Path.cwd()))
        if not folder:
            return
        self._set_tree_root(Path(folder))

    def _open_file(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select DICOM File", str(Path.cwd()), "DICOM Files (*.dcm);;All Files (*.*)"
        )
        if not file_path:
            return
        self._load_dicom(Path(file_path))

    def _set_tree_root(self, path: Path) -> None:
        self._fs_model.setRootPath(str(path))
        source_index = self._fs_model.index(str(path))
        self._tree.setRootIndex(self._proxy_model.mapFromSource(source_index))

    def _tree_double_clicked(self, index: QtCore.QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(index)
        path = Path(self._fs_model.filePath(source_index))
        if path.is_dir():
            self._set_tree_root(path)
            return
        self._load_dicom(path)

    def _toggle_sidebar(self) -> None:
        self._set_sidebar_collapsed(not self._sidebar_collapsed)

    def _set_sidebar_collapsed(self, collapsed: bool) -> None:
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

    def _set_loading_state(self, loading: bool, message: Optional[str] = None) -> None:
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
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _load_dicom(self, path: Path) -> None:
        if not path.exists():
            self.statusBar().showMessage(f"File not found: {path}", 3000)
            return

        if self._load_on_main_thread:
            self._set_loading_state(True, f"Loading {path.name}...")
            try:
                series = load_dicom_series(path, load_pixels=not self._lazy_decode_enabled)
            except DicomLoadError as exc:
                self._set_loading_state(False)
                self.statusBar().showMessage(str(exc), 4000)
                return
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

    def _on_load_finished(self, series: Optional[DicomSeries], error: Optional[str]) -> None:
        self._set_loading_state(False)
        self._loader = None
        self._loader_thread = None

        if error:
            self.statusBar().showMessage(error, 4000)
            return
        if series is None:
            self.statusBar().showMessage("Failed to load DICOM.", 3000)
            return
        self._apply_loaded_series(series)

    def _apply_loaded_series(self, series: DicomSeries) -> None:
        self._series = series
        self._current_path = series.metadata.path
        self._fps = series.metadata.fps or 30.0
        self._frame_index = 0
        self._frame_cache.clear()
        self._last_ai_result = None

        self._update_metadata_tabs(series)
        self._update_slider()
        self._render_frame()
        self._prefetch_around(self._frame_index)
        self._update_status()

    def _update_metadata_tabs(self, series: DicomSeries) -> None:
        patient = asdict(series.patient)
        metadata = asdict(series.metadata)

        self._tab_patient.setPlainText("\n".join(f"{k}: {v}" for k, v in patient.items() if v))
        self._tab_series.setPlainText("\n".join(f"{k}: {v}" for k, v in metadata.items() if v))
        self._tab_technical.setPlainText("\n".join(f"{k}: {v}" for k, v in metadata.get("additional", {}).items()))
        self._ai_table.setRowCount(0)
        self._ai_raw.setPlainText("")

    def _update_slider(self) -> None:
        if not self._series or self._series.frame_count == 0:
            self._slider.setMaximum(0)
            self._frame_label.setText("Frame 0/0")
            return
        total = self._series.frame_count
        self._slider.blockSignals(True)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, total - 1))
        self._slider.setValue(self._frame_index)
        self._slider.blockSignals(False)
        self._frame_label.setText(f"Frame {self._frame_index + 1}/{total}")

    def _render_frame(self) -> None:
        if not self._series or self._series.frame_count == 0:
            self._viewer.set_empty()
            return

        key = (str(self._current_path), self._frame_index)
        image = self._frame_cache.get(key)
        if image is None:
            try:
                frame = self._series.get_frame(self._frame_index)
            except Exception as exc:
                self._viewer.set_empty(f"Failed to render frame: {exc}")
                return
            image = qimage_from_array(frame)
            self._frame_cache.put(key, image)

        self._viewer.set_image(image)
        self._viewer.set_frame_info(self._frame_index, self._series.frame_count)

        if self._last_ai_result:
            self._viewer.set_overlay_boxes(self._last_ai_result.boxes)
        else:
            self._viewer.clear_overlays()

        self._update_status()

    def _prefetch_around(self, index: int, radius: int = 2) -> None:
        if not self._series or self._series.frame_count == 0:
            return

        max_index = self._series.frame_count - 1
        targets = [i for i in range(index - radius, index + radius + 1) if 0 <= i <= max_index]
        for i in targets:
            key = (str(self._current_path), i)
            if key in self._frame_cache:
                continue
            task = _PrefetchTask(self._frame_cache, key, self._series.get_frame, i)
            self._prefetch_pool.start(task)

    def _slider_changed(self, value: int) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self._frame_index = max(0, min(value, self._series.frame_count - 1))
        self._render_frame()
        self._prefetch_around(self._frame_index)

    def _prev_frame(self) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self._frame_index = (self._frame_index - 1) % self._series.frame_count
        self._slider.setValue(self._frame_index)

    def _next_frame(self) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self._frame_index = (self._frame_index + 1) % self._series.frame_count
        self._slider.setValue(self._frame_index)

    def _toggle_play(self) -> None:
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

    def _tick(self) -> None:
        if not self._playing:
            return
        self._next_frame()

    def _run_ai(self) -> None:
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
        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.finished.connect(self._ai_worker.deleteLater)
        self._ai_thread.finished.connect(self._ai_thread.deleteLater)
        self._ai_thread.start()

    def _on_ai_finished(self, result) -> None:
        self.statusBar().showMessage(f"AI finished: {result.status}", 3000)
        self._ai_worker = None
        self._ai_thread = None

        if result.ai_result is None:
            self._last_ai_result = None
            self._viewer.clear_overlays()
            return

        self._last_ai_result = result.ai_result
        self._apply_ai_result(result.ai_result)

    def _apply_ai_result(self, ai_result: AiResult) -> None:
        self._ai_table.setRowCount(0)
        for measurement in ai_result.measurements:
            row = self._ai_table.rowCount()
            self._ai_table.insertRow(row)
            self._ai_table.setItem(row, 0, QtWidgets.QTableWidgetItem(measurement.name))
            self._ai_table.setItem(row, 1, QtWidgets.QTableWidgetItem(measurement.value))
            self._ai_table.setItem(row, 2, QtWidgets.QTableWidgetItem(measurement.unit or ""))

        self._ai_raw.setPlainText(str(ai_result.raw))
        self._viewer.set_overlay_boxes(ai_result.boxes)

    def _export_ai_csv(self) -> None:
        if not self._last_ai_result:
            self.statusBar().showMessage("No AI results to export.", 2000)
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "results.csv", "CSV Files (*.csv)")
        if not path:
            return

        lines = ["name,value,unit"]
        for m in self._last_ai_result.measurements:
            lines.append(f"{m.name},{m.value},{m.unit or ''}")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.statusBar().showMessage("CSV exported.", 2000)

    def _export_ai_txt(self) -> None:
        if not self._last_ai_result:
            self.statusBar().showMessage("No AI results to export.", 2000)
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export TXT", "results.txt", "Text Files (*.txt)")
        if not path:
            return

        lines = [f"{m.name}: {m.value} {m.unit or ''}".strip() for m in self._last_ai_result.measurements]
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.statusBar().showMessage("TXT exported.", 2000)


class _PrefetchTask(QtCore.QRunnable):
    def __init__(
        self,
        cache: LruFrameCache[Tuple[str, int]],
        key: Tuple[str, int],
        loader: Callable[[int], np.ndarray],
        index: int,
    ) -> None:
        super().__init__()
        self._cache = cache
        self._key = key
        self._loader = loader
        self._index = index

    def run(self) -> None:
        try:
            frame = self._loader(self._index)
        except Exception:
            return
        image = qimage_from_array(frame)
        self._cache.put(self._key, image)
