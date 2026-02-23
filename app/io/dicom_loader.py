from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

try:
    from pydicom.pixel_data_handlers.util import get_frame as dicom_get_frame
except Exception:
    dicom_get_frame = None

from app.models.types import DicomMetadata, DicomSeries, PatientInfo


class DicomLoadError(RuntimeError):
    pass


def load_dicom_series(
    path: Path,
    *,
    load_pixels: bool = True,
    force: bool = False,
) -> DicomSeries:
    """
    Load DICOM metadata and optionally pixel data.
    Returns a DicomSeries with raw_frames set when load_pixels=True.
    """
    if not path.exists():
        raise DicomLoadError(f"File not found: {path}")

    try:
        read_kwargs: Dict[str, Any] = {"force": force}
        if not load_pixels:
            read_kwargs["stop_before_pixels"] = True
        ds = pydicom.dcmread(str(path), **read_kwargs)
    except InvalidDicomError as exc:
        raise DicomLoadError(f"Invalid DICOM: {exc}") from exc
    except Exception as exc:
        raise DicomLoadError(f"Failed to read DICOM: {exc}") from exc

    patient = extract_patient_info(ds)
    metadata = extract_metadata(ds, path)

    series = DicomSeries(metadata=metadata, patient=patient)

    if load_pixels:
        frames = extract_pixel_array(ds)
        frames = normalize_frames(frames, metadata.photometric_interpretation)
        series.raw_frames = frames
    else:
        series.frame_count_override = metadata.frame_count
        read_frame_only = os.getenv("DICOM_LAZY_FRAME_ONLY", "1") == "1"
        if dicom_get_frame is None:
            read_frame_only = False
        cache_frames = os.getenv("DICOM_LAZY_CACHE_FRAMES", "1") == "1"
        series.frame_loader = build_lazy_frame_loader(
            path,
            force=force,
            read_frame_only=read_frame_only,
            cache_frames=cache_frames,
        )

    return series


def extract_pixel_array(ds: pydicom.Dataset) -> np.ndarray:
    """
    Extract pixel array from a DICOM dataset.
    """
    try:
        frames = ds.pixel_array
    except Exception as exc:
        raise DicomLoadError(f"Failed to decode pixel data: {exc}") from exc

    return frames


def get_frame_count(ds: pydicom.Dataset) -> int:
    value = getattr(ds, "NumberOfFrames", None)
    if value is None:
        return 1
    try:
        count = int(value)
        return count if count > 0 else 1
    except Exception:
        return 1


def build_lazy_frame_loader(
    path: Path,
    *,
    force: bool = False,
    read_frame_only: bool = True,
    cache_frames: bool = True,
) -> Callable[[int], np.ndarray]:
    ds_cache: Dict[str, Optional[pydicom.Dataset]] = {"ds": None}
    frames_cache: Dict[str, Optional[np.ndarray]] = {"frames": None}
    lock = RLock()

    def _load(index: int) -> np.ndarray:
        with lock:
            ds = ds_cache["ds"]
            if ds is None:
                try:
                    ds = pydicom.dcmread(str(path), force=force)
                except InvalidDicomError as exc:
                    raise DicomLoadError(f"Invalid DICOM: {exc}") from exc
                except Exception as exc:
                    raise DicomLoadError(f"Failed to read DICOM: {exc}") from exc
                ds_cache["ds"] = ds

            frame_count = get_frame_count(ds)
            photometric = getattr(ds, "PhotometricInterpretation", None)
            if index < 0 or index >= frame_count:
                raise IndexError(f"Frame index out of range: {index}")

            if read_frame_only:
                try:
                    if dicom_get_frame is not None and frame_count > 1:
                        raw = dicom_get_frame(ds, index)
                    else:
                        raw = ds.pixel_array[index] if frame_count > 1 else ds.pixel_array
                except Exception as exc:
                    raise DicomLoadError(f"Failed to decode pixel data: {exc}") from exc
                frame = normalize_frames(raw, photometric)
                return frame[0]

            frames = frames_cache["frames"]
            if frames is None:
                frames = normalize_frames(extract_pixel_array(ds), photometric)
                if cache_frames:
                    frames_cache["frames"] = frames

            if frames.shape[0] <= 1:
                return frames[0]
            return frames[index]

    return _load


def normalize_frames(frames: np.ndarray, photometric_interpretation: Optional[str] = None) -> np.ndarray:
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
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def extract_patient_info(ds: pydicom.Dataset) -> PatientInfo:
    def _get(tag: str) -> Optional[str]:
        value = getattr(ds, tag, None)
        if value is None:
            return None
        return str(value)

    return PatientInfo(
        name=_get("PatientName"),
        patient_id=_get("PatientID"),
        birth_date=_get("PatientBirthDate"),
        sex=_get("PatientSex"),
        institution=_get("InstitutionName"),
        study_date=_get("StudyDate"),
        study_time=_get("StudyTime"),
        study_description=_get("StudyDescription"),
        series_description=_get("SeriesDescription"),
    )


def extract_metadata(ds: pydicom.Dataset, path: Path) -> DicomMetadata:
    fps, frame_time = get_fps_and_frame_time(ds)
    frame_count = get_frame_count(ds)

    additional: Dict[str, Any] = {
        "Manufacturer": getattr(ds, "Manufacturer", None),
        "ModelName": getattr(ds, "ManufacturerModelName", None),
        "BodyPartExamined": getattr(ds, "BodyPartExamined", None),
    }

    transfer_syntax = None
    if hasattr(ds, "file_meta") and ds.file_meta is not None:
        transfer_syntax = str(getattr(ds.file_meta, "TransferSyntaxUID", None))

    return DicomMetadata(
        path=path,
        modality=str(getattr(ds, "Modality", None)) if hasattr(ds, "Modality") else None,
        sop_instance_uid=str(getattr(ds, "SOPInstanceUID", None))
        if hasattr(ds, "SOPInstanceUID")
        else None,
        series_instance_uid=str(getattr(ds, "SeriesInstanceUID", None))
        if hasattr(ds, "SeriesInstanceUID")
        else None,
        study_instance_uid=str(getattr(ds, "StudyInstanceUID", None))
        if hasattr(ds, "StudyInstanceUID")
        else None,
        frame_time_ms=frame_time,
        fps=fps,
        rows=int(getattr(ds, "Rows", 0)) if hasattr(ds, "Rows") else None,
        cols=int(getattr(ds, "Columns", 0)) if hasattr(ds, "Columns") else None,
        frame_count=frame_count,
        photometric_interpretation=str(getattr(ds, "PhotometricInterpretation", None))
        if hasattr(ds, "PhotometricInterpretation")
        else None,
        transfer_syntax=transfer_syntax,
        additional={k: v for k, v in additional.items() if v is not None},
    )


def get_fps_and_frame_time(ds: pydicom.Dataset) -> Tuple[float, Optional[float]]:
    """
    Return (fps, frame_time_ms) if present, otherwise defaults to 30fps.
    """
    if hasattr(ds, "RecommendedDisplayFrameRate"):
        try:
            fps = float(ds.RecommendedDisplayFrameRate)
            return fps, None
        except Exception:
            pass

    if hasattr(ds, "FrameTime"):
        try:
            frame_time_ms = float(ds.FrameTime)
            if frame_time_ms > 0:
                return 1000.0 / frame_time_ms, frame_time_ms
        except Exception:
            pass

    return 30.0, None
