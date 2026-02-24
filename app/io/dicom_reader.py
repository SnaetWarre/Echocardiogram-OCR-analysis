from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

from app.io.errors import DicomLoadError


def read_dataset(path: Path, *, force: bool = False, load_pixels: bool = True) -> pydicom.Dataset:
    if not path.exists():
        raise DicomLoadError(f"File not found: {path}")

    read_kwargs: Dict[str, Any] = {"force": force}
    if not load_pixels:
        read_kwargs["stop_before_pixels"] = True
    try:
        return pydicom.dcmread(str(path), **read_kwargs)
    except InvalidDicomError as exc:
        raise DicomLoadError(f"Invalid DICOM: {exc}") from exc
    except Exception as exc:
        raise DicomLoadError(f"Failed to read DICOM: {exc}") from exc


def extract_pixel_array(ds: pydicom.Dataset) -> np.ndarray:
    try:
        return ds.pixel_array
    except Exception as exc:
        raise DicomLoadError(f"Failed to decode pixel data: {exc}") from exc


def get_frame_count(ds: pydicom.Dataset) -> int:
    value = getattr(ds, "NumberOfFrames", None)
    if value is None:
        return 1
    try:
        count = int(value)
        return count if count > 0 else 1
    except Exception:
        return 1


def get_photometric(ds: pydicom.Dataset) -> Optional[str]:
    return getattr(ds, "PhotometricInterpretation", None)
