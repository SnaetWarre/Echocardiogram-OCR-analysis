from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.io.dicom_loader import load_dicom_series
from app.io.errors import DicomLoadError
from app.models.types import AiMeasurement, AiResult, DicomSeries, OverlayBox, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import PipelineManager
from app.pipeline.startup_services import StartupServices
from app.pipeline.validation_label_writer import ValidationLabelWriter
from app.pipeline.validation_pipeline import (
    DEFAULT_GUI_OCR_ENGINE,
    GUI_OCR_ENGINE_NAMES,
    build_gui_ocr_comparison_manager,
    build_gui_ocr_manager,
)
from app.ui.components.controls import ControlsWidget
from app.ui.components.metadata_tabs import MetadataTabsWidget
from app.ui.components.sidebar import SidebarWidget
from app.ui.components.validation_stats import ValidationStatsWidget
from app.ui.dialogs.validation_dialog import ValidationDialog
from app.ui.state import ViewerState
from app.ui.theme import apply_theme
from app.ui.validation_queue import build_validation_queue
from app.ui.widgets.image_viewer import ImageViewer
from app.ui.workers import AiRunWorker, BatchTestWorker, DicomLoadWorker, PrefetchTask, ValidationPrefetchWorker
from app.utils.cache import LruFrameCache


OVERLAY_MODES = ("off", "roi", "lines", "detailed")
OVERLAY_MODE_LABELS: dict[str, str] = {
    "off": "Off",
    "roi": "ROI Only",
    "lines": "Lines",
    "detailed": "Detailed",
}
ENGINE_OVERLAY_COLORS: dict[str, str] = {
    "surya": "#F59E0B",
    "paddleocr": "#3B82F6",
    "easyocr": "#10B981",
    "tesseract": "#8B5CF6",
}
OVERLAY_UNCERTAIN_COLOR = "#EF4444"
OVERLAY_DEFAULT_COLOR = "#F59E0B"


class MainWindow(QtWidgets.QMainWindow):
    """The main application window for the DICOM viewer."""

    def __init__(self, startup_services: StartupServices | None = None) -> None:
        super().__init__()
        self.setWindowTitle("DICOM Cine Viewer")
        self.resize(1400, 900)
        self._startup_services = startup_services

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
        self._ai_run_mode = "overlay"
        self._validation_pipeline_manager: PipelineManager | None = None
        self._validation_dialog: ValidationDialog | None = None
        self._validation_writer = ValidationLabelWriter()
        self._validation_queue: list[Path] = []
        self._validation_queue_active = False
        self._validation_queue_mode = "review"
        self._pending_validation_path: Path | None = None
        self._validation_waiting_review = False
        self._active_validation_dialog_submitted = False
        self._active_validation_dialog_path: Path | None = None
        self._batch_export_files = 0
        self._batch_export_measurements = 0
        self._batch_thread: QtCore.QThread | None = None
        self._batch_worker: BatchTestWorker | None = None
        self._prefetch_validation_thread: QtCore.QThread | None = None
        self._prefetch_validation_worker: ValidationPrefetchWorker | None = None
        self._prefetched_validation_items: dict[Path, tuple[DicomSeries, PipelineResult]] = {}
        self._prefetch_validation_active_path: Path | None = None
        self._validation_prefetch_limit = 1
        self._selected_ocr_engines: tuple[str, ...] = (DEFAULT_GUI_OCR_ENGINE,)
        self._validation_manager_selection: tuple[str, ...] = ()
        self._ocr_engine_button: QtWidgets.QToolButton | None = None
        self._ocr_engine_actions: dict[str, QtGui.QAction] = {}
        self._overlay_mode = "off"
        self._overlay_mode_button: QtWidgets.QToolButton | None = None
        self._overlay_mode_actions: dict[str, QtGui.QAction] = {}

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
        self._state.validation_stats_changed.connect(self._on_validation_stats_changed)
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
        self._sidebar.folder_selected.connect(self._on_folder_selected)
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

        self._build_toolbar()

        bottom_panel = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        self._controls = ControlsWidget(self._state)
        bottom_layout.addWidget(self._controls)
        self._tabs = MetadataTabsWidget(self._state)
        bottom_layout.addWidget(self._tabs, stretch=1)

        self._content_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.addWidget(self._viewer)
        self._content_splitter.addWidget(bottom_panel)
        self._content_splitter.setStretchFactor(0, 3)
        self._content_splitter.setStretchFactor(1, 1)
        self._content_splitter.setSizes([600, 200])
        right_layout.addWidget(self._content_splitter, stretch=1)

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
        self._validation_stats = ValidationStatsWidget()
        self._validation_stats.setVisible(self._state.ai_enabled)
        self._status.addPermanentWidget(self._validation_stats)

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
            self._add_ocr_engine_selector(toolbar)
            self._add_overlay_mode_selector(toolbar)
            toolbar.addSeparator()
            act_cycle_overlay = QtGui.QAction(self)
            act_cycle_overlay.setShortcut(QtGui.QKeySequence("O"))
            act_cycle_overlay.triggered.connect(self._cycle_overlay_mode)
            self.addAction(act_cycle_overlay)
            act_run_ai = QtGui.QAction(self._icon("ai_run"), "Run AI", self)
            act_run_ai.triggered.connect(self._run_ai)
            toolbar.addAction(act_run_ai)
            act_run_validation = QtGui.QAction(self._icon("ai_run"), "OCR Validation", self)
            act_run_validation.setShortcut(QtGui.QKeySequence("V"))
            act_run_validation.triggered.connect(self._run_validation)
            toolbar.addAction(act_run_validation)
            self.addAction(act_run_validation)
            act_run_export = QtGui.QAction(self._icon("ai_run"), "OCR Batch Export", self)
            act_run_export.triggered.connect(self._run_ocr_batch_export)
            toolbar.addAction(act_run_export)
            self._update_ocr_engine_selector_enabled()

    @staticmethod
    def _ocr_engine_label(engine_name: str) -> str:
        labels = {
            "surya": "Surya",
            "paddleocr": "PaddleOCR",
            "easyocr": "EasyOCR",
            "tesseract": "Tesseract",
        }
        return labels.get(engine_name, engine_name)

    def _add_ocr_engine_selector(self, toolbar: QtWidgets.QToolBar) -> None:
        button = QtWidgets.QToolButton(self)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(self._icon("ai_run"))
        menu = QtWidgets.QMenu(button)

        self._ocr_engine_actions = {}
        for engine_name in GUI_OCR_ENGINE_NAMES:
            action = menu.addAction(self._ocr_engine_label(engine_name))
            action.setCheckable(True)
            action.setChecked(engine_name in self._selected_ocr_engines)
            action.toggled.connect(
                lambda checked, current_engine=engine_name: self._on_ocr_engine_toggled(
                    current_engine,
                    checked,
                )
            )
            self._ocr_engine_actions[engine_name] = action

        button.setMenu(menu)
        self._ocr_engine_button = button
        self._update_ocr_engine_button_text()
        toolbar.addWidget(button)

    def _selected_ocr_engine_names(self) -> tuple[str, ...]:
        if not self._ocr_engine_actions:
            return self._selected_ocr_engines
        selected = tuple(
            engine_name
            for engine_name in GUI_OCR_ENGINE_NAMES
            if self._ocr_engine_actions.get(engine_name) is not None
            and self._ocr_engine_actions[engine_name].isChecked()
        )
        return selected or self._selected_ocr_engines

    def _update_ocr_engine_button_text(self) -> None:
        if self._ocr_engine_button is None:
            return
        selected = self._selected_ocr_engine_names()
        if len(selected) == 1:
            text = f"OCR: {self._ocr_engine_label(selected[0])}"
        else:
            text = f"OCR: Compare ({len(selected)})"
        tooltip_lines = [
            "Select one or more OCR engines.",
            "Multiple selections run side-by-side comparison.",
            "",
            "Selected:",
            *(f"- {self._ocr_engine_label(engine_name)}" for engine_name in selected),
        ]
        self._ocr_engine_button.setText(text)
        self._ocr_engine_button.setToolTip("\n".join(tooltip_lines))

    def _update_ocr_engine_selector_enabled(self) -> None:
        if self._ocr_engine_button is None:
            return
        busy = bool(
            (self._ai_thread and self._ai_thread.isRunning())
            or self._validation_queue_active
            or self._validation_waiting_review
        )
        self._ocr_engine_button.setEnabled(not busy)

    def _set_selected_ocr_engines(self, engine_names: tuple[str, ...]) -> None:
        selected_set = set(engine_names)
        selected = tuple(
            engine_name
            for engine_name in GUI_OCR_ENGINE_NAMES
            if engine_name in selected_set
        ) or (DEFAULT_GUI_OCR_ENGINE,)

        for engine_name, action in self._ocr_engine_actions.items():
            action.blockSignals(True)
            action.setChecked(engine_name in selected)
            action.blockSignals(False)

        if selected == self._selected_ocr_engines:
            self._update_ocr_engine_button_text()
            return
        self._selected_ocr_engines = selected
        self._validation_pipeline_manager = None
        self._validation_manager_selection = ()
        self._state.pipeline_manager = None
        self._clear_prefetched_validation()
        self._update_ocr_engine_button_text()
    
    def _on_ocr_engine_toggled(self, engine_name: str, checked: bool) -> None:
        if checked:
            selected = self._selected_ocr_engine_names()
            self._set_selected_ocr_engines(selected)
        else:
            remaining = tuple(
                name
                for name in GUI_OCR_ENGINE_NAMES
                if name != engine_name
                and self._ocr_engine_actions.get(name) is not None
                and self._ocr_engine_actions[name].isChecked()
            )
            if not remaining:
                action = self._ocr_engine_actions.get(engine_name)
                if action is not None:
                    action.blockSignals(True)
                    action.setChecked(True)
                    action.blockSignals(False)
                self.statusBar().showMessage("Keep at least one OCR engine selected.", 2500)
                return
            self._set_selected_ocr_engines(remaining)

        selected_labels = [self._ocr_engine_label(name) for name in self._selected_ocr_engine_names()]
        if len(selected_labels) == 1:
            message = f"OCR engine set to {selected_labels[0]}."
        else:
            message = "OCR comparison mode: " + ", ".join(selected_labels)
        self.statusBar().showMessage(message, 3000)

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

    # --- Overlay mode management ---

    def _add_overlay_mode_selector(self, toolbar: QtWidgets.QToolBar) -> None:
        button = QtWidgets.QToolButton(self)
        button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(self._icon("zoom_fit"))
        button.setToolTip("Overlay mode (O to cycle)")
        menu = QtWidgets.QMenu(button)
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        self._overlay_mode_actions = {}
        for mode_key in OVERLAY_MODES:
            action = menu.addAction(OVERLAY_MODE_LABELS[mode_key])
            action.setCheckable(True)
            action.setChecked(mode_key == self._overlay_mode)
            action.triggered.connect(
                lambda _checked, m=mode_key: self._set_overlay_mode(m)
            )
            group.addAction(action)
            self._overlay_mode_actions[mode_key] = action
        button.setMenu(menu)
        self._overlay_mode_button = button
        self._update_overlay_mode_button_text()
        toolbar.addWidget(button)

    def _update_overlay_mode_button_text(self) -> None:
        if self._overlay_mode_button is None:
            return
        label = OVERLAY_MODE_LABELS.get(self._overlay_mode, "Off")
        self._overlay_mode_button.setText(f"Overlay: {label}")

    def _set_overlay_mode(self, mode: str) -> None:
        if mode not in OVERLAY_MODES:
            mode = "off"
        if mode == self._overlay_mode:
            return
        self._overlay_mode = mode
        for key, action in self._overlay_mode_actions.items():
            action.blockSignals(True)
            action.setChecked(key == mode)
            action.blockSignals(False)
        self._update_overlay_mode_button_text()
        result = self._state.last_ai_result
        seg_info = ""
        if result is not None and mode in ("lines", "detailed"):
            seg_mode = result.raw.get("segmentation_mode", "unknown")
            line_h = result.raw.get("target_line_height_px", "?")
            seg_info = f" ({seg_mode}, {line_h}px)"
        label = OVERLAY_MODE_LABELS[mode]
        self.statusBar().showMessage(f"Overlay: {label}{seg_info}", 2500)
        self._refresh_viewer_overlays()

    def _cycle_overlay_mode(self) -> None:
        idx = OVERLAY_MODES.index(self._overlay_mode) if self._overlay_mode in OVERLAY_MODES else -1
        next_mode = OVERLAY_MODES[(idx + 1) % len(OVERLAY_MODES)]
        self._set_overlay_mode(next_mode)

    # --- Overlay box building ---

    @staticmethod
    def _truncate_overlay_text(text: str, *, limit: int = 28) -> str:
        compact = " ".join(str(text).split()).strip()
        if len(compact) <= limit:
            return compact
        return compact[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _coerce_overlay_bbox(raw_bbox: object) -> tuple[float, float, float, float] | None:
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
            return None
        try:
            x, y, width, height = (float(value) for value in raw_bbox)
        except (TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        return x, y, width, height

    @staticmethod
    def _line_overlay_color(entry: dict[str, object], uncertain: bool) -> str:
        if uncertain:
            return OVERLAY_UNCERTAIN_COLOR
        engine = str(entry.get("ocr_engine", "")).strip().lower()
        return ENGINE_OVERLAY_COLORS.get(engine, OVERLAY_DEFAULT_COLOR)

    def _build_viewer_overlay_boxes(self, result: AiResult) -> list[OverlayBox]:
        if self._overlay_mode == "off":
            return []

        roi_boxes = [box for box in result.boxes if box.label == "measurement_roi"]
        if self._overlay_mode == "roi":
            return roi_boxes

        boxes = list(roi_boxes)
        line_predictions = result.raw.get("line_predictions")
        if not isinstance(line_predictions, list):
            return boxes

        comparison_lines = self._collect_comparison_overlay_lines(result)

        for index, entry in enumerate(line_predictions, start=1):
            if not isinstance(entry, dict):
                continue
            bbox = self._coerce_overlay_bbox(entry.get("line_bbox"))
            if bbox is None:
                continue
            raw_order = entry.get("order")
            line_index = (raw_order + 1) if isinstance(raw_order, int) else index
            uncertain = bool(entry.get("uncertain", False))

            if self._overlay_mode == "lines":
                label = None
            else:
                prefix = "?" if uncertain else ""
                line_text = self._truncate_overlay_text(str(entry.get("text", "")).strip(), limit=20)
                label = f"{prefix}L{line_index}"
                if line_text:
                    label = f"{label}: {line_text}"

            boxes.append(
                OverlayBox(
                    x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3],
                    label=label, confidence=None,
                    color=self._line_overlay_color(entry, uncertain),
                )
            )

        if self._overlay_mode == "detailed" and comparison_lines:
            boxes.extend(comparison_lines)

        return boxes

    def _collect_comparison_overlay_lines(self, result: AiResult) -> list[OverlayBox]:
        engine_comparison = result.raw.get("engine_comparison")
        if not isinstance(engine_comparison, list):
            return []
        primary_engine = str(result.raw.get("primary_ocr_engine", "")).strip().lower()
        extra: list[OverlayBox] = []
        for row in engine_comparison:
            if not isinstance(row, dict):
                continue
            engine_name = str(row.get("engine", "")).strip().lower()
            if engine_name == primary_engine:
                continue
            preds = row.get("line_predictions")
            if not isinstance(preds, list):
                continue
            color = ENGINE_OVERLAY_COLORS.get(engine_name, "#6B7280")
            for idx, pred in enumerate(preds, start=1):
                if not isinstance(pred, dict):
                    continue
                bbox = self._coerce_overlay_bbox(pred.get("line_bbox"))
                if bbox is None:
                    continue
                line_text = self._truncate_overlay_text(str(pred.get("text", "")).strip(), limit=22)
                raw_order = pred.get("order")
                li = (raw_order + 1) if isinstance(raw_order, int) else idx
                label = f"[{engine_name}] L{li}"
                if line_text:
                    label = f"{label}: {line_text}"
                extra.append(OverlayBox(
                    x=bbox[0], y=bbox[1] + 2, width=bbox[2], height=bbox[3],
                    label=label, confidence=None, color=color,
                ))
        return extra

    def _refresh_viewer_overlays(self) -> None:
        if self._state.last_ai_result is None:
            self._viewer.clear_overlays()
            return
        self._viewer.set_overlay_boxes(self._build_viewer_overlay_boxes(self._state.last_ai_result))

    # --- Loading Logic ---
    def _on_loading_state_changed(self, loading: bool, message: str) -> None:
        if message:
            self.statusBar().showMessage(message)
        if loading:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._update_ocr_engine_selector_enabled()

    def _on_folder_selected(self, folder: Path) -> None:
        if not folder.exists() or not folder.is_dir():
            self.statusBar().showMessage(f"Folder not found: {folder}", 3000)
            return
        self._sidebar.set_tree_root(folder)
        dicom_files = self._sidebar.list_dicom_files()
        if not dicom_files:
            self.statusBar().showMessage("No DICOM files found in this folder tree.", 3000)
            return
        self.statusBar().showMessage(f"Found {len(dicom_files)} DICOM files.", 2500)
        self._load_dicom(dicom_files[0])

    def _load_dicom(self, path: Path) -> None:
        if not path.exists():
            self.statusBar().showMessage(f"File not found: {path}", 3000)
            if self._validation_queue_active:
                self._pending_validation_path = None
                QtCore.QTimer.singleShot(0, self._advance_validation_queue)
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
                if self._validation_queue_active:
                    self._pending_validation_path = None
                    QtCore.QTimer.singleShot(0, self._advance_validation_queue)
                return
            except Exception as exc:
                self._log_event(f"Load failed (unexpected): {path} :: {exc}")
                self._state.set_loading(False)
                self._state.report_error(
                    "Load Error", f"Unexpected error while loading file: {exc}"
                )
                if self._validation_queue_active:
                    self._pending_validation_path = None
                    QtCore.QTimer.singleShot(0, self._advance_validation_queue)
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
        self._loader_thread.finished.connect(self._on_loader_thread_finished)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)
        self._loader_thread.start()

    def _on_load_finished(self, series: DicomSeries | None, error: str | None) -> None:
        self._state.set_loading(False)

        if error or series is None:
            message = error or "Failed to load DICOM."
            self._log_event(f"Load failed (worker): {message}")
            self._state.report_error("Load Error", message)
            if self._validation_queue_active:
                self._pending_validation_path = None
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
        if (
            self._validation_queue_active
            and self._pending_validation_path is not None
            and series.metadata.path == self._pending_validation_path
        ):
            QtCore.QTimer.singleShot(0, self._start_pending_validation_run)
            return
        if self._validation_queue_active and self._validation_queue_mode == "review":
            QtCore.QTimer.singleShot(0, self._start_validation_prefetch)

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
        self._viewer.set_overlay_boxes(self._build_viewer_overlay_boxes(result))

    @QtCore.Slot(int, int, int, float, float)
    def _on_validation_stats_changed(
        self,
        correct_count: int,
        total_count: int,
        validated_frames: int,
        accuracy: float,
        high_score: float,
    ) -> None:
        _ = correct_count
        _ = validated_frames
        _ = high_score
        self._validation_stats.set_stats(accuracy, total_count)

    def _run_ai(self) -> None:
        if not self._state.ai_enabled:
            QtWidgets.QMessageBox.information(
                self, "AI Disabled", "AI pipeline is not enabled in environment."
            )
            return
        try:
            manager = self._ensure_validation_manager()
        except Exception as exc:
            self._state.report_error("OCR Setup Error", str(exc))
            return
        self._start_ai_run(
            manager=manager,
            loading_message="Running AI inference...",
            mode="overlay",
        )

    def _run_validation(self) -> None:
        if not self._state.ai_enabled:
            QtWidgets.QMessageBox.information(
                self, "AI Disabled", "Enable AI mode to run OCR validation."
            )
            return
        try:
            _ = self._ensure_validation_manager()
        except Exception as exc:
            self._state.report_error("Validation Setup Error", str(exc))
            return

        if self._ai_thread and self._ai_thread.isRunning():
            self.statusBar().showMessage("AI is already running.", 2000)
            return
        if self._validation_waiting_review:
            self.statusBar().showMessage("Finish the current validation dialog first.", 2000)
            return

        queue = self._build_validation_queue()
        if not queue:
            self.statusBar().showMessage("No DICOM files found for validation queue.", 3000)
            return

        default_labels = Path.cwd() / "labels" / "exact_lines.json"
        default_path = str(default_labels)
        selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Labels To",
            default_path,
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not selected_path:
            return

        selected_output = Path(selected_path)
        if selected_output.suffix.lower() != ".json":
            selected_output = selected_output.with_suffix(".json")

        self._validation_writer = ValidationLabelWriter(output_path=selected_output)
        self._state.reset_validation_session()
        self._validation_queue = queue
        self._validation_queue_active = True
        self._validation_queue_mode = "review"
        self._pending_validation_path = None
        self._validation_waiting_review = False
        self.statusBar().showMessage(
            f"Validation queue started with {len(self._validation_queue)} files. Saving to: {selected_output.name}",
            4000,
        )
        self._update_ocr_engine_selector_enabled()
        self._advance_validation_queue()

    def _run_ocr_batch_export(self) -> None:
        if not self._state.ai_enabled:
            QtWidgets.QMessageBox.information(
                self, "AI Disabled", "Enable AI mode to run OCR batch export."
            )
            return
        try:
            _ = self._ensure_validation_manager()
        except Exception as exc:
            self._state.report_error("OCR Export Setup Error", str(exc))
            return
        if self._ai_thread and self._ai_thread.isRunning():
            self.statusBar().showMessage("AI is already running.", 2000)
            return
        if self._validation_waiting_review:
            self.statusBar().showMessage("Finish the current validation dialog first.", 2000)
            return

        queue = self._build_validation_queue()
        if not queue:
            self.statusBar().showMessage("No DICOM files found for OCR export queue.", 3000)
            return

        default_name = datetime.now().strftime("ocr_labels_%Y%m%d_%H%M%S.json")
        default_path = str(Path.cwd() / "labels" / default_name)
        selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save OCR Labels As",
            default_path,
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not selected_path:
            return

        selected_output = Path(selected_path)
        if selected_output.suffix.lower() != ".json":
            selected_output = selected_output.with_suffix(".json")

        self._validation_writer = ValidationLabelWriter(output_path=selected_output)
        self._validation_queue = queue
        self._validation_queue_active = True
        self._validation_queue_mode = "export"
        self._pending_validation_path = None
        self._validation_waiting_review = False
        self._batch_export_files = 0
        self._batch_export_measurements = 0
        self.statusBar().showMessage(
            f"OCR export started with {len(self._validation_queue)} files.",
            3000,
        )
        self._update_ocr_engine_selector_enabled()
        self._advance_validation_queue()

    def _build_validation_queue(self) -> list[Path]:
        current_path = self._state.current_path
        candidates = self._sidebar.list_dicom_files()
        return build_validation_queue(candidates, current_path)

    def _clear_prefetched_validation(self) -> None:
        self._prefetched_validation_items.clear()
        self._prefetch_validation_active_path = None

    def _start_validation_prefetch(self) -> None:
        if not self._validation_queue_active or self._validation_queue_mode != "review":
            return
        if self._validation_waiting_review:
            return
        if not self._validation_queue:
            return
        if self._prefetch_validation_thread and self._prefetch_validation_thread.isRunning():
            return

        path: Path | None = None
        for candidate in self._validation_queue[: self._validation_prefetch_limit]:
            if candidate in self._prefetched_validation_items:
                continue
            path = candidate
            break
        if path is None:
            return

        manager = self._ensure_validation_manager()
        self._prefetch_validation_active_path = path
        self._prefetch_validation_thread = QtCore.QThread(self)
        self._prefetch_validation_worker = ValidationPrefetchWorker(
            manager,
            path,
            not self._state.lazy_decode_enabled,
        )
        self._prefetch_validation_worker.moveToThread(self._prefetch_validation_thread)
        self._prefetch_validation_thread.started.connect(self._prefetch_validation_worker.run)
        self._prefetch_validation_worker.finished.connect(self._deliver_validation_prefetch_result)
        self._prefetch_validation_worker.finished.connect(self._prefetch_validation_thread.quit)
        self._prefetch_validation_worker.finished.connect(self._prefetch_validation_worker.deleteLater)
        self._prefetch_validation_thread.finished.connect(self._on_validation_prefetch_thread_finished)
        self._prefetch_validation_thread.finished.connect(self._prefetch_validation_thread.deleteLater)
        self._prefetch_validation_thread.start()

    @QtCore.Slot(object, object, object, object)
    def _deliver_validation_prefetch_result(
        self,
        path_obj: object,
        series_obj: object,
        result_obj: object,
        error_obj: object,
    ) -> None:
        if not isinstance(path_obj, Path):
            return
        if error_obj is not None:
            return
        if not isinstance(series_obj, DicomSeries):
            return
        if not isinstance(result_obj, PipelineResult):
            return

        self._prefetched_validation_items[path_obj] = (series_obj, result_obj)

    @QtCore.Slot()
    def _on_validation_prefetch_thread_finished(self) -> None:
        self._prefetch_validation_worker = None
        self._prefetch_validation_thread = None
        self._prefetch_validation_active_path = None
        if self._validation_queue_active and self._validation_queue_mode == "review":
            QtCore.QTimer.singleShot(0, self._start_validation_prefetch)

    def _advance_validation_queue(self) -> None:
        if not self._validation_queue_active:
            return
        if self._ai_thread and self._ai_thread.isRunning():
            return
        if self._loader_thread and self._loader_thread.isRunning():
            return
        if self._validation_waiting_review:
            return
        if not self._validation_queue:
            self._finish_validation_queue()
            return

        next_path = self._validation_queue.pop(0)
        self._pending_validation_path = next_path
        remaining = len(self._validation_queue) + 1
        self.statusBar().showMessage(f"Preparing {next_path.name} ({remaining} remaining)...")
        if (
            self._validation_queue_mode == "review"
            and next_path in self._prefetched_validation_items
        ):
            series, result = self._prefetched_validation_items.pop(next_path)
            self._pending_validation_path = None
            self._state.set_series(series)
            self._state.set_loading(False)
            self._on_ai_finished(result)
            return
        if self._state.current_path == next_path:
            self._start_pending_validation_run()
            return
        self._load_dicom(next_path)

    def _start_pending_validation_run(self) -> None:
        if not self._validation_queue_active:
            return
        path = self._pending_validation_path
        if path is None:
            return
        if self._state.current_path != path:
            return
        manager = self._ensure_validation_manager()
        self._pending_validation_path = None
        if self._validation_queue_mode == "export":
            loading_message = "Running OCR export..."
            mode = "export"
        else:
            loading_message = "Running OCR validation..."
            mode = "validation"
        series = self._state.series
        frame_count = series.frame_count if series is not None else 0
        frame_limit: int | None = None
        active_pipeline = manager.active()
        if active_pipeline is not None:
            config = getattr(active_pipeline, "config", None)
            parameters = getattr(config, "parameters", {}) if config is not None else {}
            raw_limit_obj = parameters.get("max_frames")
            raw_limit: int | str | float | None
            if isinstance(raw_limit_obj, (int, str, float)) or raw_limit_obj is None:
                raw_limit = raw_limit_obj
            else:
                raw_limit = None
            try:
                parsed_limit = int(raw_limit) if raw_limit is not None else 0
            except (TypeError, ValueError):
                parsed_limit = 0
            if parsed_limit > 0:
                frame_limit = parsed_limit
        if frame_count > 0:
            if frame_limit is not None and frame_count > frame_limit:
                loading_message = (
                    f"{loading_message} ({path.name}: scanning {frame_limit}/{frame_count} frames)"
                )
            else:
                suffix = "frame" if frame_count == 1 else "frames"
                loading_message = f"{loading_message} ({path.name}: {frame_count} {suffix})"
        self._start_ai_run(
            manager=manager,
            loading_message=loading_message,
            mode=mode,
            dicom_path=path,
        )

    def _finish_validation_queue(self) -> None:
        queue_mode = self._validation_queue_mode
        exported_files = self._batch_export_files
        exported_measurements = self._batch_export_measurements
        self._validation_queue_active = False
        self._validation_queue_mode = "review"
        self._pending_validation_path = None
        self._validation_waiting_review = False
        self._validation_queue = []
        self._clear_prefetched_validation()
        self._batch_export_files = 0
        self._batch_export_measurements = 0
        self._update_ocr_engine_selector_enabled()

        if queue_mode == "export":
            summary = (
                "OCR export complete.\n\n"
                f"Processed files: {exported_files}\n"
                f"Saved measurements: {exported_measurements}\n"
                f"Saved to: {self._validation_writer.output_path}"
            )
            QtWidgets.QMessageBox.information(self, "OCR Export Complete", summary)
            return

        session = self._state.validation_session
        summary = (
            "Validation queue complete.\n\n"
            f"Validated frames: {session.total_validated_frames}\n"
            f"Verified measurements: {session.total_reviewed_measurements}\n"
            f"Session accuracy: {session.accuracy * 100:.1f}%\n"
            f"Highest score seen: {session.highest_accuracy * 100:.1f}%\n"
            f"Saved to: {self._validation_writer.output_path}"
        )
        QtWidgets.QMessageBox.information(self, "Validation Queue Complete", summary)

    def _start_ai_run(
        self,
        *,
        manager: PipelineManager,
        loading_message: str,
        mode: str,
        dicom_path: Path | None = None,
    ) -> None:
        path = dicom_path or self._state.current_path
        if path is None:
            self.statusBar().showMessage("Select a DICOM file first.", 2000)
            return
        if self._ai_thread and self._ai_thread.isRunning():
            self.statusBar().showMessage("AI is already running.", 2000)
            return

        self._state.set_loading(True, loading_message)
        self._ai_run_mode = mode
        self._log_event(f"Starting {mode} AI run on: {path}")

        request = PipelineRequest(dicom_path=path)
        self._ai_thread = QtCore.QThread(self)
        self._ai_worker = AiRunWorker(manager, request)
        self._ai_worker.moveToThread(self._ai_thread)
        self._ai_thread.started.connect(self._ai_worker.run)
        self._ai_worker.finished.connect(self._on_ai_finished)
        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.finished.connect(self._ai_worker.deleteLater)
        self._ai_worker.failed.connect(self._on_ai_failed)
        self._ai_worker.failed.connect(self._ai_thread.quit)
        self._ai_worker.failed.connect(self._ai_worker.deleteLater)
        self._ai_thread.finished.connect(self._on_ai_thread_finished)
        self._ai_thread.finished.connect(self._ai_thread.deleteLater)
        self._ai_thread.start()

    def _ensure_validation_manager(self) -> PipelineManager:
        selected_engines = self._selected_ocr_engine_names()
        if (
            self._validation_pipeline_manager is not None
            and self._validation_manager_selection == selected_engines
        ):
            return self._validation_pipeline_manager
        surya_engine = self._startup_services.surya_engine if self._startup_services else None
        if len(selected_engines) > 1:
            self._validation_pipeline_manager = build_gui_ocr_comparison_manager(
                ocr_engine_names=selected_engines,
                surya_engine=surya_engine,
            )
        else:
            self._validation_pipeline_manager = build_gui_ocr_manager(
                ocr_engine_name=selected_engines[0],
                surya_engine=surya_engine,
            )
        self._validation_manager_selection = selected_engines
        self._state.pipeline_manager = self._validation_pipeline_manager
        return self._validation_pipeline_manager

    @QtCore.Slot(str)
    def _on_ai_failed(self, message: str) -> None:
        self._state.set_loading(False)
        self._log_event(f"AI failed: {message}")
        self._state.report_error("AI Error", message)

    @QtCore.Slot(object)
    def _on_ai_finished(self, result_obj: object) -> None:
        self._state.set_loading(False)

        if not isinstance(result_obj, PipelineResult):
            self._state.report_error("AI Error", "AI worker returned an invalid result payload.")
            return
        result = result_obj

        if result.status != "ok" or result.ai_result is None:
            message = result.error or "Failed to run AI."
            self._log_event(f"AI failed: {message}")
            self._state.report_error("AI Error", message)
            return

        ai_result = result.ai_result
        self._log_event(f"AI completed with {len(ai_result.measurements)} measurements.")
        self._state.apply_ai_result(ai_result)
        if self._ai_run_mode == "validation":
            self._open_validation_dialog(result.dicom_path, ai_result)
            return
        if self._ai_run_mode == "export":
            try:
                _ = self._validation_writer.append(result.dicom_path, ai_result.measurements)
            except Exception as exc:
                self._validation_queue_active = False
                self._validation_queue_mode = "review"
                self._validation_queue = []
                self._pending_validation_path = None
                self._state.report_error("OCR Export Save Error", str(exc))
                return
            self._batch_export_files += 1
            self._batch_export_measurements += len(ai_result.measurements)
            if self._validation_queue_active:
                remaining = len(self._validation_queue)
                self.statusBar().showMessage(
                    f"Exported {len(ai_result.measurements)} measurements "
                    f"for {result.dicom_path.name}. "
                    f"{remaining} files remaining.",
                    2500,
                )

    @QtCore.Slot()
    def _on_loader_thread_finished(self) -> None:
        self._loader = None
        self._loader_thread = None
        self._update_ocr_engine_selector_enabled()
        if self._validation_queue_active and self._pending_validation_path is None:
            QtCore.QTimer.singleShot(0, self._advance_validation_queue)

    @QtCore.Slot()
    def _on_ai_thread_finished(self) -> None:
        self._ai_worker = None
        self._ai_thread = None
        self._update_ocr_engine_selector_enabled()
        if (
            self._validation_queue_active
            and self._ai_run_mode in {"validation", "export"}
            and not self._validation_waiting_review
        ):
            QtCore.QTimer.singleShot(0, self._advance_validation_queue)

    def _open_validation_dialog(self, dicom_path: Path, ai_result: AiResult) -> None:
        if self._validation_dialog is not None:
            self._validation_dialog.close()
        dialog = ValidationDialog(dicom_path=dicom_path, ai_result=ai_result, parent=self)
        dialog.submitted.connect(self._on_validation_submitted)
        dialog.finished.connect(self._on_validation_dialog_closed)
        anchor = self.mapToGlobal(QtCore.QPoint(self.width() - dialog.width() - 30, 70))
        dialog.move(anchor)
        dialog.show()
        dialog.raise_()
        self._validation_dialog = dialog
        self._validation_waiting_review = True
        self._active_validation_dialog_submitted = False
        self._active_validation_dialog_path = dicom_path
        self._update_ocr_engine_selector_enabled()
        QtCore.QTimer.singleShot(0, self._start_validation_prefetch)

    @QtCore.Slot(int)
    def _on_validation_dialog_closed(self, _result: int) -> None:
        was_waiting_review = self._validation_waiting_review
        was_submitted = self._active_validation_dialog_submitted

        if self._validation_queue_active and was_waiting_review and not was_submitted:
            self._validation_queue_active = False
            self._validation_queue_mode = "review"
            self._validation_queue = []
            self._pending_validation_path = None
            self.statusBar().showMessage("Validation queue stopped.", 3000)

        self._validation_waiting_review = False
        self._active_validation_dialog_submitted = False
        self._active_validation_dialog_path = None
        self._validation_dialog = None
        self._update_ocr_engine_selector_enabled()

    @QtCore.Slot(object, object, int, int, bool)
    def _on_validation_submitted(
        self,
        dicom_path_obj: object,
        measurements_obj: object,
        approved_count: int,
        incorrect_count: int,
        skip_output: bool,
    ) -> None:
        if not isinstance(dicom_path_obj, Path):
            self._state.report_error("Validation Error", "Validation submission contained no path.")
            return

        if (
            self._active_validation_dialog_path is not None
            and dicom_path_obj != self._active_validation_dialog_path
        ):
            self._state.report_error(
                "Validation Error",
                (
                    "Validation submission path did not match the active dialog. "
                    "The submission was ignored to prevent writing labels to the wrong file."
                ),
            )
            return

        measurements = [
            line for line in measurements_obj if isinstance(line, str)
        ] if isinstance(measurements_obj, list) else []

        output_path: Path | None = None
        if not skip_output:
            try:
                output_path = self._validation_writer.append(dicom_path_obj, measurements)
            except Exception as exc:
                self._state.report_error("Validation Save Error", str(exc))
                return

        self._active_validation_dialog_submitted = True
        self._validation_waiting_review = False

        accuracy, is_new_high = self._state.record_validation(
            dicom_path_obj,
            approved_count=approved_count,
            corrected_count=incorrect_count,
            measurements=measurements,
        )
        if self._state.last_ai_result is not None:
            base = self._state.last_ai_result
            self._state.apply_ai_result(
                AiResult(
                    model_name=base.model_name,
                    created_at=base.created_at,
                    boxes=base.boxes,
                    measurements=[],
                    raw={**base.raw, "validated": True, "validated_lines": measurements},
                )
            )

        if self._validation_queue_active:
            remaining = len(self._validation_queue)
            if skip_output:
                action = "Skipped false positive"
            else:
                action = f"Saved {len(measurements)} measurements"
            self.statusBar().showMessage(
                f"{action} for {dicom_path_obj.name}. "
                f"{remaining} files remaining.",
                2500,
            )
            QtCore.QTimer.singleShot(0, self._advance_validation_queue)
            return

        session = self._state.validation_session
        if skip_output:
            summary = (
                f"Marked {dicom_path_obj.name} as false positive / no measurement box.\n\n"
                f"Session accuracy: {accuracy * 100:.1f}%\n"
                f"Highest score seen: {session.highest_accuracy * 100:.1f}%\n"
                f"Validated frames: {session.total_validated_frames}"
            )
        else:
            summary = (
                f"Saved {len(measurements)} measurements to:\n{output_path}\n\n"
                f"Session accuracy: {accuracy * 100:.1f}%\n"
                f"Highest score seen: {session.highest_accuracy * 100:.1f}%\n"
                f"Validated frames: {session.total_validated_frames}"
            )
        if is_new_high:
            summary += "\n\nNew highest score this session."
        QtWidgets.QMessageBox.information(self, "Validation Summary", summary)

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
            self._viewer.set_overlay_boxes(self._build_viewer_overlay_boxes(self._state.last_ai_result))
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
