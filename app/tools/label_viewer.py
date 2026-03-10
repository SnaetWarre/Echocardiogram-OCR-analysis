"""
Quick labeling tool for DICOM measurement overlays.

Usage:
  python -m app.tools.label_viewer --folder /path/to/dicoms --output labels/exact_lines.json

Flow:
  1. Select folder (or pass --folder)
  2. View each DICOM frame
  3. Type exact displayed measurement lines, one per line
  4. Save and continue
  5. Output is written as canonical JSON exact-line labels

Dataset format:
{
  "version": 1,
  "task": "exact_roi_measurement_transcription",
  "files": [
    {
      "file_name": "94106955_0016.dcm",
      "file_path": "/absolute/or/relative/path/to/file.dcm",
      "measurements": [
        {"order": 1, "text": "1 IVSd 0.9 cm"},
        {"order": 2, "text": "2 LVIDd 5.4 cm"}
      ]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6 import QtCore, QtGui, QtWidgets

from app.io.dicom_loader import load_dicom_series
from app.ui.widgets.image_viewer import ImageViewer
from app.utils.image import qimage_from_array


DATASET_VERSION = 1
DATASET_TASK = "exact_roi_measurement_transcription"
DEFAULT_SPLIT = "validation"


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _canonicalize_line(text: str) -> str | None:
    stripped = _normalize_space(text)
    if not stripped:
        return None
    stripped = stripped.replace(r"\,", " ")
    stripped = stripped.replace(r"\%", " %")
    stripped = re.sub(r"\\text\{([^}]*)\}", r"\1", stripped)
    stripped = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", stripped)
    stripped = re.sub(
        r"(\d)(%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)\b",
        r"\1 \2",
        stripped,
        flags=re.IGNORECASE,
    )
    return _normalize_space(stripped)


def _empty_dataset() -> dict[str, Any]:
    return {
        "version": DATASET_VERSION,
        "task": DATASET_TASK,
        "files": [],
    }


def _validate_dataset_shape(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object.")
    version = data.get("version")
    task = data.get("task")
    files = data.get("files")

    if version != DATASET_VERSION:
        raise ValueError(f"Unsupported dataset version: {version!r}")
    if task != DATASET_TASK:
        raise ValueError(f"Unsupported dataset task: {task!r}")
    if not isinstance(files, list):
        raise ValueError("Dataset field 'files' must be a list.")
    return data


def _load_dataset(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_dataset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON: {exc}") from exc
    return _validate_dataset_shape(data)


def _make_record(file_path: Path, measurements: list[str], split: str) -> dict[str, Any]:
    return {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "split": _normalize_space(split).lower(),
        "measurements": [
            {"order": index + 1, "text": line}
            for index, line in enumerate(measurements)
        ],
    }


def _upsert_record(dataset: dict[str, Any], record: dict[str, Any]) -> None:
    files = dataset["files"]
    file_path = str(record["file_path"])
    for index, existing in enumerate(files):
        if not isinstance(existing, dict):
            continue
        if str(existing.get("file_path", "")) == file_path:
            files[index] = record
            return
    files.append(record)


def _sort_dataset_files(dataset: dict[str, Any]) -> None:
    dataset["files"].sort(
        key=lambda item: (
            str(item.get("file_name", "")),
            str(item.get("file_path", "")),
        )
    )


def _save_dataset(path: Path, dataset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _sort_dataset_files(dataset)
    path.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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
        self._dataset = _empty_dataset()
        self._split = DEFAULT_SPLIT

        self.setWindowTitle(f"Label Viewer - {folder.name}")
        self.resize(1000, 760)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._viewer = ImageViewer()
        self._viewer.setMinimumHeight(420)
        layout.addWidget(self._viewer)

        self._info_label = QtWidgets.QLabel("")
        self._info_label.setObjectName("labelInfo")
        layout.addWidget(self._info_label)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._status_label)

        hint = QtWidgets.QLabel(
            "Type exact displayed measurement lines, one per line. "
            "Preserve visible numeric prefixes like 1, 2, 3. "
            "Labels are saved into one shared dataset file with a split per record. "
            "Ctrl+Enter: save and next. Ctrl+Shift+S: skip file. Ctrl+Q: quit."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

        self._input = QtWidgets.QPlainTextEdit()
        self._input.setPlaceholderText(
            "1 TR Vmax 1.9 m/s\n2 TR maxPG 14 mmHg"
        )
        self._input.setMaximumHeight(160)
        self._input.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self._input)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)

        self._btn_prev = QtWidgets.QPushButton("Previous")
        self._btn_prev.clicked.connect(self._previous)
        btn_layout.addWidget(self._btn_prev)

        self._btn_skip = QtWidgets.QPushButton("Skip")
        self._btn_skip.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self._btn_skip.clicked.connect(self._skip)
        btn_layout.addWidget(self._btn_skip)

        self._btn_next = QtWidgets.QPushButton("Save & Next (Ctrl+Enter)")
        self._btn_next.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self._btn_next.clicked.connect(self._save_and_next)
        btn_layout.addWidget(self._btn_next)

        layout.addLayout(btn_layout)

        self._input.installEventFilter(self)

        self._load_dataset_or_show_error()
        self._load_dicom_list()
        self._show_split_prompt()
        self._show_current()

    def _load_dataset_or_show_error(self) -> None:
        try:
            self._dataset = _load_dataset(self._output)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid label file",
                f"Could not load existing label file:\n{exc}\n\nA new dataset will be started.",
            )
            self._dataset = _empty_dataset()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self._input and event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QtGui.QKeyEvent):
                key = key_event.key()
                mods = key_event.modifiers()
                if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                    if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
                        self._save_and_next()
                        return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if (
            event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self._save_and_next()
            return
        if event.matches(QtGui.QKeySequence.StandardKey.Quit):
            self.close()
            return
        super().keyPressEvent(event)

    def _show_split_prompt(self) -> None:
        split, ok = QtWidgets.QInputDialog.getText(
            self,
            "Dataset split",
            "Split for newly saved records:",
            text=self._split,
        )
        if ok:
            cleaned = _normalize_space(split).lower()
            if cleaned:
                self._split = cleaned

    def _load_dicom_list(self) -> None:
        self._files = sorted(self._folder.rglob("*.dcm"))
        if not self._files:
            self._files = sorted(self._folder.rglob("*.Documents"))
        self._index = 0

    def _current_path(self) -> Path | None:
        if 0 <= self._index < len(self._files):
            return self._files[self._index]
        return None

    def _record_for_path(self, path: Path) -> dict[str, Any] | None:
        for record in self._dataset.get("files", []):
            if not isinstance(record, dict):
                continue
            if str(record.get("file_path", "")) == str(path):
                return record
        return None

    def _load_existing_measurements(self, path: Path) -> list[str]:
        record = self._record_for_path(path)
        if not record:
            return []
        measurements = record.get("measurements", [])
        if not isinstance(measurements, list):
            return []
        lines: list[tuple[int, str]] = []
        for idx, item in enumerate(measurements):
            if not isinstance(item, dict):
                continue
            text = _canonicalize_line(str(item.get("text", "")) or "")
            if not text:
                continue
            order = item.get("order")
            order_value = int(order) if isinstance(order, int) else idx + 1
            lines.append((order_value, text))
        lines.sort(key=lambda pair: pair[0])
        return [text for _, text in lines]

    def _show_current(self) -> None:
        if self._index >= len(self._files):
            self._info_label.setText("Done! No more files.")
            self._status_label.setText(
                f"Saved dataset: {self._output} | Total labeled files: {len(self._dataset.get('files', []))}"
            )
            self._viewer.set_empty("All files labeled.")
            self._input.clear()
            self._btn_next.setEnabled(False)
            self._btn_skip.setEnabled(False)
            self._btn_prev.setEnabled(len(self._files) > 0)
            return

        path = self._files[self._index]
        existing_lines = self._load_existing_measurements(path)

        self._info_label.setText(f"[{self._index + 1}/{len(self._files)}] {path.name}")
        existing_record = self._record_for_path(path)
        existing_split = ""
        if existing_record is not None:
            existing_split = _normalize_space(str(existing_record.get("split", ""))).lower()

        if existing_lines:
            self._status_label.setText(
                f"Existing label found for this file in {self._output.name}"
                + (f" [split={existing_split}]" if existing_split else "")
            )
        else:
            self._status_label.setText(f"Writing to {self._output} [split={self._split}]")

        self._input.setPlainText("\n".join(existing_lines))
        self._input.setFocus()

        self._btn_prev.setEnabled(self._index > 0)

        try:
            self._series = load_dicom_series(path, load_pixels=True)
            frame = self._series.get_frame(0)
            qimg = qimage_from_array(frame)
            self._viewer.set_image(qimg)
            self._viewer.set_frame_info(0, self._series.frame_count)
        except Exception as exc:
            self._viewer.set_empty(str(exc))
            self._series = None

    def _collect_input_lines(self) -> list[str]:
        raw_lines = self._input.toPlainText().splitlines()
        normalized: list[str] = []
        for line in raw_lines:
            canonical = _canonicalize_line(line)
            if canonical:
                normalized.append(canonical)
        return normalized

    def _save_current(self) -> bool:
        path = self._current_path()
        if path is None:
            return False

        measurements = self._collect_input_lines()
        record = _make_record(path, measurements, self._split)
        _upsert_record(self._dataset, record)

        try:
            _save_dataset(self._output, self._dataset)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Save failed",
                f"Could not write label dataset:\n{exc}",
            )
            return False

        self._status_label.setText(
            f"Saved {path.name} to {self._output.name} ({len(measurements)} lines)"
        )
        return True

    def _save_and_next(self) -> None:
        if self._index >= len(self._files):
            return
        if not self._save_current():
            return
        self._index += 1
        self._show_current()

    def _skip(self) -> None:
        if self._index >= len(self._files):
            return
        self._index += 1
        self._show_current()

    def _previous(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._show_current()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quick labeling of DICOM measurement overlays into canonical JSON exact-line labels."
    )
    parser.add_argument("--folder", type=Path, default=None, help="Folder with DICOM files.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("labels/exact_lines.json"),
        help="Output JSON label file.",
    )
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    folder = args.folder
    if folder is None or not folder.is_dir():
        folder_raw = QtWidgets.QFileDialog.getExistingDirectory(
            None, "Select DICOM Folder", str(Path.cwd())
        )
        if not folder_raw:
            return 0
        folder = Path(folder_raw)

    window = LabelViewerWindow(folder=folder, output=args.output)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
