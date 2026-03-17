from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np
from PySide6 import QtCore

from app.io.dicom_loader import load_dicom_series
from app.io.errors import DicomLoadError
from app.models.types import PipelineRequest
from app.pipeline.ai_pipeline import PipelineManager
from app.validation.queue import collect_dicom_files
from app.utils.cache import LruFrameCache
from app.utils.image import qimage_from_array


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
    failed = QtCore.Signal(str)

    def __init__(self, manager: PipelineManager, request: PipelineRequest) -> None:
        super().__init__()
        self._manager = manager
        self._request = request

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = self._manager.run(self._request)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class ValidationPrefetchWorker(QtCore.QObject):
    finished = QtCore.Signal(object, object, object, object)  # path, series, result, error

    def __init__(self, manager: PipelineManager, path: Path, load_pixels: bool) -> None:
        super().__init__()
        self._manager = manager
        self._path = path
        self._load_pixels = load_pixels

    @QtCore.Slot()
    def run(self) -> None:
        try:
            series = load_dicom_series(self._path, load_pixels=self._load_pixels)
        except Exception as exc:
            self.finished.emit(self._path, None, None, f"Failed to load DICOM: {exc}")
            return

        try:
            result = self._manager.run(PipelineRequest(dicom_path=self._path))
        except Exception as exc:
            self.finished.emit(self._path, series, None, f"Failed to run OCR: {exc}")
            return

        self.finished.emit(self._path, series, result, None)


class ValidationPrefetchTask(QtCore.QRunnable):
    def __init__(self, manager: PipelineManager, path: Path, load_pixels: bool, callback) -> None:
        super().__init__()
        self._manager = manager
        self._path = path
        self._load_pixels = load_pixels
        self._callback = callback

    def run(self) -> None:
        try:
            series = load_dicom_series(self._path, load_pixels=self._load_pixels)
        except Exception as exc:
            self._callback(self._path, None, None, f"Failed to load DICOM: {exc}")
            return

        try:
            result = self._manager.run(PipelineRequest(dicom_path=self._path))
        except Exception as exc:
            self._callback(self._path, series, None, f"Failed to run OCR: {exc}")
            return

        self._callback(self._path, series, result, None)


class BatchTestWorker(QtCore.QObject):
    progress = QtCore.Signal(int, int, str, bool, str, float)
    finished = QtCore.Signal(int, int, float)

    def __init__(self, root: Path, load_pixels: bool, decode_first_frame: bool) -> None:
        super().__init__()
        self._root = root
        self._load_pixels = load_pixels
        self._decode_first_frame = decode_first_frame

    @QtCore.Slot()
    def run(self) -> None:
        start_all = time.perf_counter()
        files = collect_dicom_files(self._root)

        total = len(files)
        ok = 0
        for idx, path in enumerate(files, start=1):
            start = time.perf_counter()
            try:
                series = load_dicom_series(path, load_pixels=self._load_pixels)
                if self._decode_first_frame:
                    frame = series.get_frame(0)
                    _ = qimage_from_array(frame)
                duration = time.perf_counter() - start
                ok += 1
                self.progress.emit(idx, total, str(path), True, "", duration)
            except Exception as exc:
                duration = time.perf_counter() - start
                self.progress.emit(idx, total, str(path), False, str(exc), duration)

        total_time = time.perf_counter() - start_all
        self.finished.emit(ok, total, total_time)


class PrefetchTask(QtCore.QRunnable):
    def __init__(
        self,
        cache: LruFrameCache[tuple[str, int]],
        key: tuple[str, int],
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
        try:
            image = qimage_from_array(frame)
        except Exception:
            return
        self._cache.put(self._key, image)
