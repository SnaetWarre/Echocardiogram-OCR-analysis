from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.widgets.file_browser import FileFilterProxyModel
from app.ui.widgets.image_viewer import ImageViewer

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


def _build_ui(self: "MainWindow") -> None:
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
        QtCore.QDir.Filter.AllEntries
        | QtCore.QDir.Filter.NoDotAndDotDot
        | QtCore.QDir.Filter.AllDirs
    )
    self._fs_model.setRootPath(str(Path.cwd()))

    self._proxy_model = FileFilterProxyModel(self)
    self._proxy_model.setSourceModel(self._fs_model)

    self._tree = QtWidgets.QTreeView()
    self._tree.setHeaderHidden(True)
    self._tree.setAlternatingRowColors(True)
    self._tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    self._tree.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
    self._tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
    self._tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
    self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
    self._tree.doubleClicked.connect(self._tree_double_clicked)
    self._tree.setModel(self._proxy_model)
    self._tree.setRootIndex(
        self._proxy_model.mapFromSource(self._fs_model.index(str(Path.cwd())))
    )
    self._tree.header().setSectionResizeMode(
        0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
    )
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

    self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    self._slider.setMinimum(0)
    self._slider.setMaximum(0)
    self._slider.valueChanged.connect(self._slider_changed)

    self._frame_label = QtWidgets.QLabel("Frame 0/0")
    self._frame_label.setMinimumWidth(90)
    self._frame_label.setAlignment(
        QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
    )

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

    if getattr(self, "_ai_enabled", False):
        self._tabs.addTab(self._tab_ai, "AI Results")
    right_layout.addWidget(self._tabs)

    splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
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


def _icon(self: "MainWindow", name: str) -> QtGui.QIcon:
    base = Path(__file__).resolve().parent / "icons"
    path = base / f"{name}.svg"
    if path.exists():
        return QtGui.QIcon(str(path))
    return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)


def _build_toolbar(self: "MainWindow") -> None:
    toolbar = QtWidgets.QToolBar("Main")
    toolbar.setMovable(False)
    toolbar.setIconSize(QtCore.QSize(18, 18))
    toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    self.addToolBar(toolbar)

    act_open = QtGui.QAction(self._icon("open_file"), "Open File", self)
    act_folder = QtGui.QAction(self._icon("open_folder"), "Open Folder", self)
    act_toggle = QtGui.QAction(self._icon("sidebar_collapse"), "Toggle Sidebar", self)
    act_filter = QtGui.QAction(self._icon("filter"), "Toggle .dcm Filter", self)
    act_filter.setCheckable(True)
    act_filter.setChecked(self._filter_toggle.isChecked())
    act_run_ai = QtGui.QAction(self._icon("ai_run"), "Run AI", self)
    act_batch_test = QtGui.QAction(self._icon("open_folder"), "Batch Test Folder", self)
    act_batch_run = QtGui.QAction(self._icon("open_folder"), "Batch Run Viewer", self)
    act_zoom_in = QtGui.QAction(self._icon("zoom_in"), "Zoom In", self)
    act_zoom_out = QtGui.QAction(self._icon("zoom_out"), "Zoom Out", self)
    act_zoom_fit = QtGui.QAction(self._icon("zoom_fit"), "Zoom to Fit", self)

    self._act_toggle_sidebar = act_toggle
    self._act_filter = act_filter

    act_open.triggered.connect(self._open_file)
    act_folder.triggered.connect(self._open_folder)
    act_toggle.triggered.connect(self._toggle_sidebar)
    act_filter.triggered.connect(self._toggle_filter)
    if getattr(self, "_ai_enabled", False):
        act_run_ai.triggered.connect(self._run_ai)
    act_batch_test.triggered.connect(self._start_batch_test)
    act_batch_run.triggered.connect(self._start_ui_batch_run)
    act_zoom_in.triggered.connect(lambda: self._viewer.zoom(1.2))
    act_zoom_out.triggered.connect(lambda: self._viewer.zoom(1 / 1.2))
    act_zoom_fit.triggered.connect(self._viewer.zoom_to_fit)

    toolbar.addAction(act_open)
    toolbar.addAction(act_folder)
    toolbar.addAction(act_batch_test)
    toolbar.addAction(act_batch_run)
    toolbar.addSeparator()
    toolbar.addAction(act_toggle)
    toolbar.addAction(act_filter)
    toolbar.addSeparator()
    toolbar.addAction(act_zoom_in)
    toolbar.addAction(act_zoom_out)
    toolbar.addAction(act_zoom_fit)
    toolbar.addSeparator()
    if getattr(self, "_ai_enabled", False):
        toolbar.addAction(act_run_ai)
