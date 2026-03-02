from __future__ import annotations

import numpy as np


def normalize_frames(
    frames: np.ndarray, photometric_interpretation: str | None = None
) -> np.ndarray:
    """
    Normalize DICOM frames to a consistent shape and dtype uint8.
    Returns:
      - grayscale: (N, H, W)
      - color:     (N, H, W, C)
    """
    arr = np.asarray(frames)

    if arr.ndim == 2:
        arr = arr[np.newaxis, ...]
    elif arr.ndim == 3:
        photometric = str(photometric_interpretation).upper() if photometric_interpretation else ""
        color_modes = {
            "RGB",
            "YBR_FULL",
            "YBR_FULL_422",
            "YBR_PARTIAL_422",
            "YBR_PARTIAL_420",
            "YBR_ICT",
            "YBR_RCT",
        }
        if photometric in color_modes:
            if arr.shape[-1] not in (3, 4) and arr.shape[0] in (3, 4):
                arr = np.moveaxis(arr, 0, -1)
            if arr.shape[-1] in (3, 4):
                arr = arr[np.newaxis, ...]
        elif not photometric and arr.shape[-1] in (3, 4):
            arr = arr[np.newaxis, ...]

    if arr.dtype != np.uint8:
        arr = to_uint8(arr)

    if photometric_interpretation:
        photometric = str(photometric_interpretation).upper()
        if photometric == "MONOCHROME1":
            arr = 255 - arr

    return arr


def to_uint8(arr: np.ndarray) -> np.ndarray:
    """
    Convert array to uint8 using range normalization.
    """
    if arr.dtype == np.uint8:
        return arr

    arr = arr.astype(np.float32, copy=False)
    max_val = float(arr.max()) if arr.size else 0.0
    if max_val > 255:
        arr = (arr / max_val) * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)
