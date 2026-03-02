from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

from PySide6 import QtGui

K = TypeVar("K")


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    size: int
    capacity: int


class LruFrameCache(Generic[K]):
    """
    Thread-safe LRU cache for QImage/QPixmap frames.
    Stores QImage by default to reduce GPU memory pressure; callers can
    promote to QPixmap on demand.
    """

    def __init__(self, capacity: int = 128) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._lock = RLock()
        self._data: OrderedDict[K, QtGui.QImage] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._data),
                capacity=self._capacity,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: K) -> bool:
        with self._lock:
            return key in self._data

    def get(self, key: K) -> QtGui.QImage | None:
        with self._lock:
            image = self._data.get(key)
            if image is None:
                self._misses += 1
                return None
            self._hits += 1
            self._data.move_to_end(key)
            return image

    def put(self, key: K, image: QtGui.QImage) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = image
            self._evict_if_needed()

    def pop(self, key: K) -> QtGui.QImage | None:
        with self._lock:
            return self._data.pop(key, None)

    def peek(self, key: K) -> QtGui.QImage | None:
        with self._lock:
            return self._data.get(key)

    def items(self) -> Iterator[tuple[K, QtGui.QImage]]:
        with self._lock:
            return iter(self._data.items())

    def _evict_if_needed(self) -> None:
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)


class LruPixmapCache(Generic[K]):
    """
    Separate LRU cache for QPixmap when you want to cache GPU-friendly objects.
    """

    def __init__(self, capacity: int = 64) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._lock = RLock()
        self._data: OrderedDict[K, QtGui.QPixmap] = OrderedDict()

    @property
    def capacity(self) -> int:
        return self._capacity

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get(self, key: K) -> QtGui.QPixmap | None:
        with self._lock:
            pixmap = self._data.get(key)
            if pixmap is None:
                return None
            self._data.move_to_end(key)
            return pixmap

    def put(self, key: K, pixmap: QtGui.QPixmap) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = pixmap
            self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        while len(self._data) > self._capacity:
            self._data.popitem(last=False)
