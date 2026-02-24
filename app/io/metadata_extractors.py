from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pydicom

from app.io.dicom_reader import get_frame_count
from app.models.types import DicomMetadata, PatientInfo


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
