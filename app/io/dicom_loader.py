from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
import pydicom

from app.io.dicom_reader import (
    extract_pixel_array,
    get_frame_count,
    read_dataset,
)
from app.io.errors import DicomLoadError
from app.io.frame_loaders import (
    build_lazy_frame_loader as _build_lazy_frame_loader,
    build_subprocess_frame_loader,
    default_dicom_get_frame,
)
from app.io.metadata_extractors import (
    extract_metadata,
    extract_patient_info,
    get_fps_and_frame_time,
)
from app.io.normalization import normalize_frames, to_uint8
from app.models.types import DicomMetadata, DicomSeries, PatientInfo

dicom_get_frame = default_dicom_get_frame


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
    ds = read_dataset(path, force=force, load_pixels=load_pixels)

    patient = extract_patient_info(ds)
    metadata = extract_metadata(ds, path)

    series = DicomSeries(metadata=metadata, patient=patient)

    if load_pixels:
        frames = extract_pixel_array(ds)
        frames = normalize_frames(frames, metadata.photometric_interpretation)
        series.raw_frames = frames
    else:
        series.frame_count_override = metadata.frame_count
        use_subprocess = os.getenv("DICOM_SUBPROCESS_DECODE", "0") == "1"
        if use_subprocess:
            series.frame_loader = build_subprocess_frame_loader(path, force=force)
        else:
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


def build_lazy_frame_loader(
    path: Path,
    *,
    force: bool = False,
    read_frame_only: bool = True,
    cache_frames: bool = True,
) -> Callable[[int], np.ndarray]:
    return _build_lazy_frame_loader(
        path,
        force=force,
        read_frame_only=read_frame_only,
        cache_frames=cache_frames,
        get_frame_fn=dicom_get_frame,
    )
