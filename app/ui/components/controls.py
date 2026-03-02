from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from app.models.types import DicomSeries

if TYPE_CHECKING:
    from app.ui.state import ViewerState


class ControlsWidget(QtWidgets.QFrame):
    """Widget managing playback controls and the frame slider."""

    def __init__(self, state: ViewerState) -> None:
        super().__init__()
        self._state = state
        self.setObjectName("controls")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

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

        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)

        self._frame_label = QtWidgets.QLabel("Frame 0/0")
        self._frame_label.setMinimumWidth(90)
        self._frame_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self._btn_prev)
        layout.addWidget(self._btn_play)
        layout.addWidget(self._btn_next)
        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._frame_label)

        # Connect UI interactions to State
        self._btn_prev.clicked.connect(self._state.prev_frame)
        self._btn_next.clicked.connect(self._state.next_frame)
        self._btn_play.clicked.connect(self._state.toggle_play)
        self._slider.valueChanged.connect(self._state.set_frame_index)

        # Connect State updates to UI
        self._state.series_loaded.connect(self._on_series_loaded)
        self._state.frame_changed.connect(self._update_slider_and_label)
        self._state.play_state_changed.connect(self._update_play_button)
        self._state.loading_state_changed.connect(self._update_loading_state)

    def _icon(self, name: str) -> QtGui.QIcon:
        base = Path(__file__).resolve().parent.parent / "icons"
        path = base / f"{name}.svg"
        if path.exists():
            return QtGui.QIcon(str(path))
        return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay)

    def _on_series_loaded(self, series: DicomSeries) -> None:
        if not series or series.frame_count == 0:
            self._slider.setMaximum(0)
            self._frame_label.setText("Frame 0/0")
            return

        total = series.frame_count
        self._slider.blockSignals(True)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, total - 1))
        self._slider.setValue(0)
        self._slider.blockSignals(False)

        self._frame_label.setText(f"Frame 1/{total}")

    def _update_slider_and_label(self, frame_index: int) -> None:
        series = self._state.series
        if not series or series.frame_count == 0:
            return

        self._slider.blockSignals(True)
        self._slider.setValue(frame_index)
        self._slider.blockSignals(False)

        total = series.frame_count
        self._frame_label.setText(f"Frame {frame_index + 1}/{total}")

    def _update_play_button(self, playing: bool) -> None:
        self._btn_play.setText("Pause" if playing else "Play")
        self._btn_play.setIcon(self._icon("pause" if playing else "play"))

    def _update_loading_state(self, loading: bool, message: str) -> None:
        _ = message
        self._btn_prev.setEnabled(not loading)
        self._btn_play.setEnabled(not loading)
        self._btn_next.setEnabled(not loading)
        self._slider.setEnabled(not loading)
        if loading:
            self._btn_play.setText("Play")
            self._btn_play.setIcon(self._icon("play"))
