from dataclasses import dataclass
from typing import Any

import numpy as np
import pydicom


@dataclass
class OverlayBitmap:
    group: int
    data: np.ndarray
    origin: tuple[int, int] | None


@dataclass
class GraphicAnnotation:
    graphic_type: str
    points: list[float]
    units: str


@dataclass
class UltrasoundRegion:
    spatial_format: int | None
    data_type: int | None
    min_x0: int | None
    min_y0: int | None
    max_x1: int | None
    max_y1: int | None


@dataclass
class DicomContent:
    frames: np.ndarray
    fps: float
    patient_info: dict[str, str]
    overlays: list[OverlayBitmap]
    graphics: list[GraphicAnnotation]
    regions: list[UltrasoundRegion]


def get_fps(ds: pydicom.Dataset, default_fps: float = 30.0) -> float:
    if "RecommendedDisplayFrameRate" in ds:
        try:
            return float(ds.RecommendedDisplayFrameRate)
        except Exception:
            pass
    if "FrameTime" in ds:
        try:
            ms = float(ds.FrameTime)
            if ms > 0:
                return 1000.0 / ms
        except Exception:
            pass
    return default_fps


def extract_patient_info(ds: pydicom.Dataset) -> dict[str, str]:
    info: dict[str, str] = {}
    tags = {
        "PatientName": "Patient's Name",
        "PatientID": "Patient ID",
        "PatientBirthDate": "Birth Date",
        "PatientSex": "Sex",
        "StudyDate": "Study Date",
        "StudyTime": "Study Time",
        "StudyDescription": "Study Description",
        "SeriesDescription": "Series Description",
        "InstitutionName": "Institution",
    }
    for tag, label in tags.items():
        if hasattr(ds, tag):
            value = getattr(ds, tag)
            if value:
                info[label] = str(value)
    return info


def extract_bitmap_overlays(ds: pydicom.Dataset) -> list[OverlayBitmap]:
    overlays: list[OverlayBitmap] = []
    for group in range(0x6000, 0x601F, 2):
        if (group, 0x3000) not in ds:
            continue
        try:
            data = ds.overlay_array(group)
            origin = None
            if (group, 0x0050) in ds:
                raw = ds[group, 0x0050].value
                if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                    origin = (int(raw[0]), int(raw[1]))
            overlays.append(OverlayBitmap(group=group, data=data, origin=origin))
        except Exception:
            continue
    return overlays


def extract_graphic_annotations(ds: pydicom.Dataset) -> list[GraphicAnnotation]:
    result: list[GraphicAnnotation] = []
    if not hasattr(ds, "GraphicAnnotationSequence"):
        return result
    try:
        for ann in ds.GraphicAnnotationSequence:
            units = str(getattr(ann, "BoundingBoxAnnotationUnits", "PIXEL"))
            if not hasattr(ann, "GraphicObjectSequence"):
                continue
            for obj in ann.GraphicObjectSequence:
                gtype = str(getattr(obj, "GraphicType", ""))
                gdata = getattr(obj, "GraphicData", None)
                if not gtype or gdata is None:
                    continue
                result.append(
                    GraphicAnnotation(
                        graphic_type=gtype,
                        points=[float(v) for v in gdata],
                        units=units,
                    )
                )
    except Exception:
        return result
    return result


def extract_ultrasound_regions(ds: pydicom.Dataset) -> list[UltrasoundRegion]:
    result: list[UltrasoundRegion] = []
    if not hasattr(ds, "SequenceOfUltrasoundRegions"):
        return result

    for region in ds.SequenceOfUltrasoundRegions:
        result.append(
            UltrasoundRegion(
                spatial_format=getattr(region, "RegionSpatialFormat", None),
                data_type=getattr(region, "RegionDataType", None),
                min_x0=getattr(region, "RegionLocationMinX0", None),
                min_y0=getattr(region, "RegionLocationMinY0", None),
                max_x1=getattr(region, "RegionLocationMaxX1", None),
                max_y1=getattr(region, "RegionLocationMaxY1", None),
            )
        )
    return result


def load_dicom_content(path: str) -> DicomContent:
    ds = pydicom.dcmread(path)
    frames = ds.pixel_array
    if frames.dtype != np.uint8:
        max_value = float(frames.max()) if frames.size else 0.0
        if max_value > 255:
            frames = (frames / max_value * 255).astype(np.uint8)
        else:
            frames = np.clip(frames, 0, 255).astype(np.uint8)

    return DicomContent(
        frames=frames,
        fps=get_fps(ds),
        patient_info=extract_patient_info(ds),
        overlays=extract_bitmap_overlays(ds),
        graphics=extract_graphic_annotations(ds),
        regions=extract_ultrasound_regions(ds),
    )
