from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class PatientInfo:
    name: Optional[str] = None
    patient_id: Optional[str] = None
    birth_date: Optional[str] = None
    sex: Optional[str] = None
    institution: Optional[str] = None
    study_date: Optional[str] = None
    study_time: Optional[str] = None
    study_description: Optional[str] = None
    series_description: Optional[str] = None


@dataclass(frozen=True)
class DicomMetadata:
    path: Path
    modality: Optional[str] = None
    sop_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    study_instance_uid: Optional[str] = None
    frame_time_ms: Optional[float] = None
    fps: Optional[float] = None
    rows: Optional[int] = None
    cols: Optional[int] = None
    frame_count: Optional[int] = None
    photometric_interpretation: Optional[str] = None
    transfer_syntax: Optional[str] = None
    additional: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameData:
    index: int
    pixels: np.ndarray
    timestamp: Optional[datetime] = None


@dataclass
class DicomSeries:
    metadata: DicomMetadata
    patient: PatientInfo
    frames: List[FrameData] = field(default_factory=list)
    raw_frames: Optional[np.ndarray] = None
    frame_loader: Optional[Callable[[int], np.ndarray]] = None
    frame_count_override: Optional[int] = None

    @property
    def frame_count(self) -> int:
        if self.raw_frames is not None:
            return int(self.raw_frames.shape[0])
        if self.frame_count_override is not None:
            return int(self.frame_count_override)
        if self.metadata.frame_count is not None:
            return int(self.metadata.frame_count)
        return len(self.frames)

    def get_frame(self, index: int) -> np.ndarray:
        if self.raw_frames is not None:
            return self.raw_frames[index]
        if self.frame_loader is not None:
            return self.frame_loader(index)
        if self.frames:
            return self.frames[index].pixels
        raise IndexError("No frames available")


@dataclass
class ViewerState:
    current_path: Optional[Path] = None
    frame_index: int = 0
    fps: float = 30.0
    zoom: float = 1.0
    playing: bool = False
    sidebar_visible: bool = True


@dataclass(frozen=True)
class OverlayBox:
    x: float
    y: float
    width: float
    height: float
    label: Optional[str] = None
    confidence: Optional[float] = None
    color: str = "#00A2FF"


@dataclass(frozen=True)
class AiMeasurement:
    name: str
    value: str
    unit: Optional[str] = None
    source: Optional[str] = None


@dataclass
class AiResult:
    model_name: str
    created_at: datetime
    boxes: List[OverlayBox] = field(default_factory=list)
    measurements: List[AiMeasurement] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRequest:
    dicom_path: Path
    output_dir: Optional[Path] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    dicom_path: Path
    status: str
    ai_result: Optional[AiResult] = None
    error: Optional[str] = None


@dataclass
class FileNode:
    path: Path
    is_dir: bool
    children: List["FileNode"] = field(default_factory=list)
