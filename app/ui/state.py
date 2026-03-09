from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from PySide6 import QtCore

from app.models.types import AiResult, DicomSeries, ValidatedLabelRecord, ValidationSession
from app.pipeline.ai_pipeline import PipelineManager, build_default_manager


class ViewerState(QtCore.QObject):
    """Central state manager for the DICOM viewer."""

    # Signals
    series_loaded = QtCore.Signal(DicomSeries)
    frame_changed = QtCore.Signal(int)
    play_state_changed = QtCore.Signal(bool)
    ai_result_ready = QtCore.Signal(AiResult)
    validation_stats_changed = QtCore.Signal(int, int, int, float, float)
    error_occurred = QtCore.Signal(str, str)
    loading_state_changed = QtCore.Signal(bool, str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._series: DicomSeries | None = None
        self._current_path: Path | None = None
        self._frame_index = 0
        self._fps = 30.0
        self._playing = False

        # Config state
        self.lazy_decode_enabled = os.getenv("DICOM_LAZY_DECODE", "1") == "1"
        self.load_on_main_thread = os.getenv("DICOM_LOAD_MAIN_THREAD", "1") == "1"
        self.prefetch_enabled = os.getenv("DICOM_PREFETCH", "0") == "1"
        self.prefetch_radius = int(os.getenv("DICOM_PREFETCH_RADIUS", "0"))
        self.prefetch_threads = int(os.getenv("DICOM_PREFETCH_THREADS", "1"))
        self.ai_enabled = os.getenv("DICOM_AI_ENABLED", "1") == "1"

        self.pipeline_manager: PipelineManager | None = (
            build_default_manager() if self.ai_enabled else None
        )
        self.last_ai_result: AiResult | None = None
        self.validation_session = ValidationSession()

        # Batch state
        self.ui_batch_running = False
        self.ui_batch_expect_render = False

    @property
    def series(self) -> DicomSeries | None:
        return self._series

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def playing(self) -> bool:
        return self._playing

    def set_series(self, series: DicomSeries) -> None:
        self._series = series
        self._current_path = series.metadata.path
        self._fps = series.metadata.fps or 30.0
        self._frame_index = 0
        self.last_ai_result = None
        self.series_loaded.emit(series)

    def set_frame_index(self, index: int) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        clamped = max(0, min(index, self._series.frame_count - 1))
        if clamped != self._frame_index:
            self._frame_index = clamped
            self.frame_changed.emit(self._frame_index)

    def next_frame(self) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self.set_frame_index((self._frame_index + 1) % self._series.frame_count)

    def prev_frame(self) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self.set_frame_index((self._frame_index - 1) % self._series.frame_count)

    def toggle_play(self) -> None:
        if not self._series or self._series.frame_count == 0:
            return
        self.set_playing(not self._playing)

    def set_playing(self, playing: bool) -> None:
        if self._playing != playing:
            self._playing = playing
            self.play_state_changed.emit(self._playing)

    def set_loading(self, loading: bool, message: str = "") -> None:
        if loading:
            self.set_playing(False)
        self.loading_state_changed.emit(loading, message)

    def report_error(self, title: str, message: str) -> None:
        self.error_occurred.emit(title, message)

    def apply_ai_result(self, result: AiResult) -> None:
        self.last_ai_result = result
        self.ai_result_ready.emit(result)

    def reset_validation_session(self) -> None:
        self.validation_session = ValidationSession()
        self.validation_stats_changed.emit(0, 0, 0, 0.0, 0.0)

    def record_validation(
        self,
        dicom_path: Path,
        approved_count: int,
        corrected_count: int,
        measurements: list[str],
    ) -> tuple[float, bool]:
        session = self.validation_session
        session.total_validated_frames += 1
        session.total_ai_correct += max(0, approved_count)
        session.total_ai_incorrect += max(0, corrected_count)
        session.session_labels.append(
            ValidatedLabelRecord(
                path=dicom_path,
                validated_at=datetime.now(timezone.utc),
                measurements=list(measurements),
            )
        )

        accuracy = session.accuracy
        is_new_high = accuracy > session.highest_accuracy
        if is_new_high:
            session.highest_accuracy = accuracy

        self.validation_stats_changed.emit(
            session.total_ai_correct,
            session.total_reviewed_measurements,
            session.total_validated_frames,
            accuracy,
            session.highest_accuracy,
        )
        return accuracy, is_new_high
