from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PySide6 import QtGui


def _to_uint8(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return image
    return np.clip(image, 0, 255).astype(np.uint8)


def _contiguous(image: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(image)


def qimage_from_array(image: np.ndarray) -> QtGui.QImage:
    """
    Safely convert a numpy array into a QImage.
    Supports grayscale (H, W) and color (H, W, 3/4).
    """
    if image is None:
        raise ValueError("image is None")

    array = np.asarray(image)

    if array.ndim == 2:
        img = _contiguous(_to_uint8(array))
        h, w = img.shape
        bytes_per_line = img.strides[0]
        return QtGui.QImage(
            img.data, w, h, bytes_per_line, QtGui.QImage.Format_Grayscale8
        ).copy()

    if array.ndim == 3 and array.shape[2] in (3, 4):
        img = _contiguous(_to_uint8(array))
        h, w, c = img.shape
        fmt = QtGui.QImage.Format_RGB888 if c == 3 else QtGui.QImage.Format_RGBA8888
        bytes_per_line = img.strides[0]
        return QtGui.QImage(img.data, w, h, bytes_per_line, fmt).copy()

    # Fallback: try to interpret any other array as grayscale
    flat = _contiguous(_to_uint8(array))
    h, w = flat.shape[:2]
    bytes_per_line = flat.strides[0]
    return QtGui.QImage(
        flat.data, w, h, bytes_per_line, QtGui.QImage.Format_Grayscale8
    ).copy()
