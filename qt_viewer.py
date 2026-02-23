import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from pydicom.errors import InvalidDicomError

from PySide6 import QtCore, QtGui, QtWidgets

from cineviewer.dicom_data import DicomContent, load_dicom_content


def _normalize_frames(frames: np.ndarray) -> np.ndarray:
    if frames.ndim == 2:
        return frames[np.newaxis, ...]
    if frames.ndim == 3 and frames.shape[-1] in (3, 4):
        return frames[np.newaxis, ...]
    return frames


class DicomLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(object, object, object)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    @QtCore.Slot()
    def run(self) -> None:
        try:
            content = load_dicom_content(self._path)
        except InvalidDicomError:
            self.finished.emit(None, "Not a valid DICOM file.", self._path)
            return
        except Exception as exc:
            self.finished.emit(None, f"Failed to load DICOM: {exc}", self._path)
            return
        self.finished.emit(content, None, self._path)


class ImageViewer(QtWidgets.QGraphicsView):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.setRenderHints(
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.SmoothPixmapTransform
            | QtGui.QPainter.TextAntialiasing
        )
        self.setBackgroundBrush(QtGui.QColor("#FAFAFA"))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

        self._empty_text = QtWidgets.QGraphicsSimpleTextItem(
            "No DICOM loaded\nOpen a folder or select a DICOM file"
        )
        self._empty_text.setBrush(QtGui.QBrush(QtGui.QColor("#8A9199")))
        font = QtGui.QFont()
        font.setPointSize(12)
        self._empty_text.setFont(font)
        self._scene.addItem(self._empty_text)
        self._center_empty_text()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._center_empty_text()
        self.fitInView(self._scene.itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)

    def _center_empty_text(self) -> None:
        rect = self._empty_text.boundingRect()
        center = self.viewport().rect().center()
        self._empty_text.setPos(
            center.x() - rect.width() / 2,
            center.y() - rect.height() / 2,
        )

    def set_image(self, qimage: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self._pixmap_item.setPixmap(pixmap)
        self._empty_text.setVisible(False)
        self.fitInView(self._pixmap_item.boundingRect(), QtCore.Qt.KeepAspectRatio)

    def set_empty(self) -> None:
        self.set_placeholder("No DICOM loaded\nOpen a folder or select a DICOM file")

    def set_placeholder(self, text: str) -> None:
        self._pixmap_item.setPixmap(QtGui.QPixmap())
        self._empty_text.setText(text)
        self._empty_text.setVisible(True)
        self._center_empty_text()


class DicomViewerApp(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DICOM Cine Viewer")
        self.resize(1280, 840)

        self._content: Optional[DicomContent] = None
        self._frames: Optional[np.ndarray] = None
        self._frame_index = 0
        self._fps = 30.0
        self._playing = False
        self._last_dir = Path.cwd()
        self._current_file: Optional[Path] = None
        self._loader_thread: Optional[QtCore.QThread] = None
        self._loader: Optional[DicomLoadWorker] = None
        self._loading_prev_has_content = False
        self._sidebar_visible = True
        self._load_on_main_thread = os.getenv("DICOM_LOAD_MAIN_THREAD", "0") == "1"

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._refresh_tree_filters()
        self._apply_theme()
        self._set_empty_state()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self._left_panel = QtWidgets.QFrame()
        self._left_panel.setObjectName("leftPanel")
        self._left_panel.setMinimumWidth(260)
        left_layout = QtWidgets.QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        self._btn_open_folder = QtWidgets.QPushButton("Open Folder")
        self._btn_open_file = QtWidgets.QPushButton("Open File")
        self._btn_open_folder.clicked.connect(self._open_folder)
        self._btn_open_file.clicked.connect(self._open_file)
        header.addWidget(self._btn_open_folder)
        header.addWidget(self._btn_open_file)
        left_layout.addLayout(header)

        self._filter_toggle = QtWidgets.QCheckBox("Show only .dcm")
        self._filter_toggle.setChecked(True)
        self._filter_toggle.stateChanged.connect(self._refresh_tree_filters)
        left_layout.addWidget(self._filter_toggle)

        self._tree = QtWidgets.QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._tree.setAlternatingRowColors(True)
        self._tree.doubleClicked.connect(self._tree_double_clicked)

        self._fs_model = QtWidgets.QFileSystemModel()
        self._fs_model.setFilter(
            QtCore.QDir.AllEntries
            | QtCore.QDir.NoDotAndDotDot
            | QtCore.QDir.AllDirs
        )
        self._fs_model.setRootPath(str(self._last_dir))
        self._tree.setModel(self._fs_model)
        self._tree.setRootIndex(self._fs_model.index(str(self._last_dir)))

        left_layout.addWidget(self._tree)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_header = QtWidgets.QHBoxLayout()
        right_header.addStretch(1)
        self._btn_toggle_sidebar = QtWidgets.QToolButton()
        self._btn_toggle_sidebar.setText("Hide Sidebar")
        self._btn_toggle_sidebar.clicked.connect(self._toggle_sidebar)
        right_header.addWidget(self._btn_toggle_sidebar)
        right_layout.addLayout(right_header)

        self._viewer = ImageViewer()
        right_layout.addWidget(self._viewer, stretch=1)

        controls = QtWidgets.QFrame()
        controls.setObjectName("controls")
        controls_layout = QtWidgets.QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 8, 12, 8)
        controls_layout.setSpacing(12)

        self._btn_prev = QtWidgets.QPushButton("Prev")
        self._btn_play = QtWidgets.QPushButton("Play")
        self._btn_next = QtWidgets.QPushButton("Next")
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

        self._info_panel = QtWidgets.QTextEdit()
        self._info_panel.setReadOnly(True)
        self._info_panel.setObjectName("infoPanel")
        right_layout.addWidget(self._info_panel)

        right_container = QtWidgets.QWidget()
        right_container.setLayout(right_layout)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self._left_panel)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        main_layout.addWidget(splitter)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #FAFAFA;
            }
            #leftPanel {
                background: #F6F7F9;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
            }
            #controls {
                background: #F6F7F9;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
            }
            #infoPanel {
                background: #FFFFFF;
                color: #5C6773;
                border: 1px solid #E1E4E8;
                border-radius: 8px;
                font-family: "Segoe UI", "Inter", "Arial", sans-serif;
                font-size: 11px;
            }
            QPushButton, QToolButton {
                background: #FF8F40;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover, QToolButton:hover {
                background: #FF9F5A;
            }
            QPushButton:pressed, QToolButton:pressed {
                background: #F57C32;
            }
            QCheckBox {
                color: #5C6773;
            }
            QTreeView {
                background: #FFFFFF;
                alternate-background-color: #F6F7F9;
                color: #5C6773;
                border: 1px solid #E1E4E8;
                border-radius: 6px;
                selection-background-color: #E6F2FF;
                selection-color: #1F2D3D;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #E1E4E8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                background: #FF8F40;
                margin: -4px 0;
                border-radius: 6px;
            }
            QLabel {
                color: #5C6773;
            }
            """
        )

    def _refresh_tree_filters(self) -> None:
        if self._filter_toggle.isChecked():
            self._fs_model.setNameFilters(["*.dcm"])
            self._fs_model.setNameFilterDisables(False)
        else:
            self._fs_model.setNameFilters([])
            self._fs_model.setNameFilterDisables(False)

        current_root = str(self._last_dir)
        self._fs_model.setRootPath(current_root)
        self._tree.setRootIndex(self._fs_model.index(current_root))

    def _open_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Folder", str(self._last_dir)
        )
        if not folder:
            return
        self._last_dir = Path(folder)
        self._fs_model.setRootPath(str(self._last_dir))
        self._tree.setRootIndex(self._fs_model.index(str(self._last_dir)))

    def _open_file(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select DICOM File",
            str(self._last_dir),
            "DICOM Files (*.dcm);;All Files (*.*)",
        )
        if not file_path:
            return
        self._load_dicom(Path(file_path))

    def _tree_double_clicked(self, index: QtCore.QModelIndex) -> None:
        path = Path(self._fs_model.filePath(index))
        if path.is_dir():
            self._last_dir = path
            self._fs_model.setRootPath(str(path))
            self._tree.setRootIndex(self._fs_model.index(str(path)))
            return
        self._load_dicom(path)

    def _toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        self._left_panel.setVisible(self._sidebar_visible)
        self._btn_toggle_sidebar.setText("Hide Sidebar" if self._sidebar_visible else "Show Sidebar")

    def _set_loading_state(self, loading: bool, message: Optional[str] = None) -> None:
        widgets = (
            self._btn_prev,
            self._btn_play,
            self._btn_next,
            self._slider,
            self._btn_open_folder,
            self._btn_open_file,
            self._btn_toggle_sidebar,
            self._tree,
            self._filter_toggle,
        )
        for widget in widgets:
            widget.setEnabled(not loading)

        if loading:
            self._timer.stop()
            self._playing = False
            self._btn_play.setText("Play")
            if message:
                self.statusBar().showMessage(message)
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _start_load_dicom(self, path: Path) -> None:
        if self._loader_thread and self._loader_thread.isRunning():
            self.statusBar().showMessage("Already loading a DICOM file.", 2000)
            return
        if not path.exists():
            self.statusBar().showMessage(f"File not found: {path}", 3000)
            return

        self._loading_prev_has_content = self._frames is not None and self._frames.size > 0
        self._set_loading_state(True, f"Loading {path.name}...")
        if not self._loading_prev_has_content:
            self._viewer.set_placeholder("Loading DICOM...")

        self._loader_thread = QtCore.QThread(self)
        self._loader = DicomLoadWorker(path)
        self._loader.moveToThread(self._loader_thread)
        self._loader_thread.started.connect(self._loader.run)
        self._loader.finished.connect(self._on_load_finished)
        self._loader.finished.connect(self._loader_thread.quit)
        self._loader.finished.connect(self._loader.deleteLater)
        self._loader_thread.finished.connect(self._loader_thread.deleteLater)
        self._loader_thread.start()

    def _on_load_finished(
        self,
        content: Optional[DicomContent],
        error: Optional[str],
        path: Path,
    ) -> None:
        self._set_loading_state(False)
        self._loader = None
        self._loader_thread = None

        if error:
            self.statusBar().showMessage(error, 4000)
            if not self._loading_prev_has_content:
                self._set_empty_state()
            else:
                self._render_frame()
            return

        if content is None:
            self.statusBar().showMessage("Failed to load DICOM.", 3000)
            if not self._loading_prev_has_content:
                self._set_empty_state()
            return

        normalized_frames = _normalize_frames(content.frames)
        content.frames = normalized_frames
        self._content = content
        self._frames = normalized_frames
        self._frame_index = 0
        self._fps = float(content.fps) if content.fps else 30.0
        self._current_file = path
        self._last_dir = path.parent

        self._update_info_panel()
        self._update_slider()
        self._update_timer_interval()
        self._render_frame()

    def _load_dicom(self, path: Path) -> None:
        if self._load_on_main_thread:
            if not path.exists():
                self.statusBar().showMessage(f"File not found: {path}", 3000)
                return

            self._loading_prev_has_content = self._frames is not None and self._frames.size > 0
            self._set_loading_state(True, f"Loading {path.name}...")
            if not self._loading_prev_has_content:
                self._viewer.set_placeholder("Loading DICOM...")

            try:
                content = load_dicom_content(path)
            except InvalidDicomError:
                self._on_load_finished(None, "Not a valid DICOM file.", path)
                return
            except Exception as exc:
                self._on_load_finished(None, f"Failed to load DICOM: {exc}", path)
                return

            self._on_load_finished(content, None, path)
            return

        self._start_load_dicom(path)

    def _update_info_panel(self) -> None:
        if not self._content:
            self._info_panel.setPlainText("")
            return
        lines = [f"{k}: {v}" for k, v in self._content.patient_info.items()]
        self._info_panel.setPlainText("\n".join(lines))

    def _update_slider(self) -> None:
        if self._frames is None or self._frames.size == 0:
            self._slider.setMaximum(0)
            self._frame_label.setText("Frame 0/0")
            return
        total = int(self._frames.shape[0])
        self._slider.blockSignals(True)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, total - 1))
        self._slider.setValue(self._frame_index)
        self._slider.blockSignals(False)
        self._frame_label.setText(f"Frame {self._frame_index + 1}/{total}")

    def _update_timer_interval(self) -> None:
        interval_ms = max(1, int(1000 / self._fps))
        self._timer.setInterval(interval_ms)

    def _render_frame(self) -> None:
        if self._frames is None or self._frames.size == 0:
            self._set_empty_state()
            return

        frame = self._frames[self._frame_index]
        qimage = self._to_qimage(frame)
        self._viewer.set_image(qimage)
        self._frame_label.setText(f"Frame {self._frame_index + 1}/{self._frames.shape[0]}")

    def _to_qimage(self, frame: np.ndarray) -> QtGui.QImage:
        frame = np.asarray(frame)

        if frame.ndim == 2:
            img = frame
            if img.dtype != np.uint8:
                img = np.clip(img, 0, 255).astype(np.uint8)
            img = np.ascontiguousarray(img)
            h, w = img.shape
            bytes_per_line = img.strides[0]
            return QtGui.QImage(
                img.data, w, h, bytes_per_line, QtGui.QImage.Format_Grayscale8
            ).copy()

        if frame.ndim == 3 and frame.shape[2] in (3, 4):
            img = frame
            if img.dtype != np.uint8:
                img = np.clip(img, 0, 255).astype(np.uint8)
            img = np.ascontiguousarray(img)
            h, w, c = img.shape
            fmt = QtGui.QImage.Format_RGB888 if c == 3 else QtGui.QImage.Format_RGBA8888
            bytes_per_line = img.strides[0]
            return QtGui.QImage(img.data, w, h, bytes_per_line, fmt).copy()

        flat = np.clip(frame, 0, 255).astype(np.uint8)
        flat = np.ascontiguousarray(flat)
        h, w = flat.shape[:2]
        bytes_per_line = flat.strides[0]
        return QtGui.QImage(
            flat.data, w, h, bytes_per_line, QtGui.QImage.Format_Grayscale8
        ).copy()

    def _set_empty_state(self) -> None:
        self._viewer.set_empty()
        self._timer.stop()
        self._playing = False
        self._btn_play.setText("Play")
        self._slider.blockSignals(True)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._frame_label.setText("Frame 0/0")
        self._info_panel.setPlainText("")

    def _slider_changed(self, value: int) -> None:
        if self._frames is None or self._frames.size == 0:
            return
        self._frame_index = max(0, min(value, self._frames.shape[0] - 1))
        self._render_frame()

    def _prev_frame(self) -> None:
        if self._frames is None or self._frames.size == 0:
            return
        self._frame_index = (self._frame_index - 1) % self._frames.shape[0]
        self._slider.setValue(self._frame_index)

    def _next_frame(self) -> None:
        if self._frames is None or self._frames.size == 0:
            return
        self._frame_index = (self._frame_index + 1) % self._frames.shape[0]
        self._slider.setValue(self._frame_index)

    def _toggle_play(self) -> None:
        if self._frames is None or self._frames.size == 0:
            return
        self._playing = not self._playing
        self._btn_play.setText("Pause" if self._playing else "Play")
        if self._playing:
            self._timer.start()
        else:
            self._timer.stop()

    def _tick(self) -> None:
        if not self._playing or self._frames is None or self._frames.size == 0:
            return
        self._frame_index = (self._frame_index + 1) % self._frames.shape[0]
        self._slider.setValue(self._frame_index)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    viewer = DicomViewerApp()
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
