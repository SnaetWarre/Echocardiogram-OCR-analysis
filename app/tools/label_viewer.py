"""
Quick labeling tool for DICOM measurement overlays.

Usage:
  python -m app.tools.label_viewer [--folder PATH] [--output labels.md]

Flow:
  1. Select folder (or pass --folder)
  2. View each DICOM frame
  3. Type measurements, one per line: "Name Value Unit" (e.g. "TR Vmax 1.9 m/s")
  4. Enter or Ctrl+Return: save and go to next file
  5. Output appended to labels.md format
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6 import QtCore, QtGui, QtWidgets

from app.io.dicom_loader import load_dicom_series
from app.ui.widgets.image_viewer import ImageViewer
from app.utils.image import qimage_from_array


def _format_measurement_line(line: str) -> str | None:
    """Format line as '-> Name Value Unit' for labels.md."""
    stripped = line.strip()
    if not stripped:
        return None
    return f"-> {stripped}"


class LabelViewerWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        folder: Path,
        output: Path,
    ) -> None:
        super().__init__()
        self._folder = folder
        self._output = output
        self._files: list[Path] = []
        self._index = 0
        self._series = None
        self._frame_index = 0

        self.setWindowTitle(f"Label Viewer - {folder.name}")
        self.resize(900, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._viewer = ImageViewer()
        self._viewer.setMinimumHeight(400)
        layout.addWidget(self._viewer)

        info = QtWidgets.QLabel("")
        info.setObjectName("labelInfo")
        layout.addWidget(info)
        self._info_label = info

        hint = QtWidgets.QLabel(
            "Type measurements, one per line: \"Name Value Unit\" (e.g. TR Vmax 1.9 m/s). "
            "Ctrl+Enter: save and next. Ctrl+Shift+S: skip file. Ctrl+Q: quit."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

        self._input = QtWidgets.QPlainTextEdit()
        self._input.setPlaceholderText("TR Vmax 1.9 m/s\nTR maxPG 14 mmHg")
        self._input.setMaximumHeight(120)
        self._input.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self._input)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        self._btn_next = QtWidgets.QPushButton("Save & Next (Ctrl+Enter)")
        self._btn_next.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self._btn_next.clicked.connect(self._save_and_next)
        self._btn_skip = QtWidgets.QPushButton("Skip")
        self._btn_skip.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self._btn_skip.clicked.connect(self._skip)
        btn_layout.addWidget(self._btn_skip)
        btn_layout.addWidget(self._btn_next)
        layout.addLayout(btn_layout)

        self._input.installEventFilter(self)

        self._load_dicom_list()
        self._show_current()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self._input and event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                mods = event.modifiers()
                if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
                    self._save_and_next()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Return and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            self._save_and_next()
            return
        if event.matches(QtGui.QKeySequence.StandardKey.Quit):
            self.close()
            return
        super().keyPressEvent(event)

    def _load_dicom_list(self) -> None:
        self._files = sorted(self._folder.rglob("*.dcm"))
        if not self._files:
            self._files = sorted(self._folder.rglob("*.Documents"))
        self._index = 0

    def _show_current(self) -> None:
        if self._index >= len(self._files):
            self._info_label.setText("Done! No more files.")
            self._viewer.set_empty("All files labeled.")
            self._input.clear()
            self._btn_next.setEnabled(False)
            self._btn_skip.setEnabled(False)
            return

        path = self._files[self._index]
        self._info_label.setText(f"[{self._index + 1}/{len(self._files)}] {path.name}")
        self._input.clear()
        self._input.setFocus()

        try:
            self._series = load_dicom_series(path, load_pixels=True)
            frame = self._series.get_frame(0)
            qimg = qimage_from_array(frame)
            self._viewer.set_image(qimg)
            self._viewer.set_frame_info(0, self._series.frame_count)
        except Exception as e:
            self._viewer.set_empty(str(e))
            self._series = None

    def _save_and_next(self) -> None:
        if self._index >= len(self._files):
            return

        path = self._files[self._index]
        lines = self._input.toPlainText().strip().splitlines()

        measurements: list[str] = []
        for line in lines:
            formatted = _format_measurement_line(line)
            if formatted:
                measurements.append(formatted)

        out_path = self._output.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as f:
            f.write(f"path: {path}\n\n")
            for m in measurements:
                f.write(f"{m}\n")
            f.write("\n--\n\n")

        self._index += 1
        self._show_current()

    def _skip(self) -> None:
        if self._index >= len(self._files):
            return
        self._index += 1
        self._show_current()


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick labeling of DICOM measurement overlays.")
    parser.add_argument("--folder", type=Path, default=None, help="Folder with DICOM files.")
    parser.add_argument("--output", type=Path, default=Path("labels.md"), help="Output file.")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    folder = args.folder
    if folder is None or not folder.is_dir():
        folder = QtWidgets.QFileDialog.getExistingDirectory(None, "Select DICOM Folder", str(Path.cwd()))
        if not folder:
            return 0
        folder = Path(folder)

    window = LabelViewerWindow(folder=folder, output=args.output)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
