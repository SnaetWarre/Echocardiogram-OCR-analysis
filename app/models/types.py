from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True)
class PatientInfo:
    name: str | None = None
    patient_id: str | None = None
    birth_date: str | None = None
    sex: str | None = None
    institution: str | None = None
    study_date: str | None = None
    study_time: str | None = None
    study_description: str | None = None
    series_description: str | None = None


@dataclass(frozen=True)
class DicomMetadata:
    path: Path
    modality: str | None = None
    sop_instance_uid: str | None = None
    series_instance_uid: str | None = None
    study_instance_uid: str | None = None
    frame_time_ms: float | None = None
    fps: float | None = None
    rows: int | None = None
    cols: int | None = None
    frame_count: int | None = None
    photometric_interpretation: str | None = None
    transfer_syntax: str | None = None
    additional: dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameData:
    index: int
    pixels: np.ndarray
    timestamp: datetime | None = None


@dataclass
class DicomSeries:
    metadata: DicomMetadata
    patient: PatientInfo
    frames: list[FrameData] = field(default_factory=list)
    raw_frames: np.ndarray | None = None
    frame_loader: Callable[[int], np.ndarray] | None = None
    frame_count_override: int | None = None

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
    current_path: Path | None = None
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
    label: str | None = None
    confidence: float | None = None
    color: str = "#00A2FF"


@dataclass(frozen=True)
class AiMeasurement:
    name: str
    value: str
    unit: str | None = None
    source: str | None = None
    order_hint: int | None = None


@dataclass(frozen=True)
class ValidatedLabelRecord:
    path: Path
    validated_at: datetime
    measurements: list[str]


@dataclass
class ValidationSession:
    total_validated_frames: int = 0
    total_ai_correct: int = 0
    total_ai_incorrect: int = 0
    session_labels: list[ValidatedLabelRecord] = field(default_factory=list)
    highest_accuracy: float = 0.0

    @property
    def total_reviewed_measurements(self) -> int:
        return self.total_ai_correct + self.total_ai_incorrect

    @property
    def accuracy(self) -> float:
        reviewed = self.total_reviewed_measurements
        if reviewed <= 0:
            return 0.0
        return self.total_ai_correct / reviewed


@dataclass
class AiResult:
    model_name: str
    created_at: datetime
    boxes: list[OverlayBox] = field(default_factory=list)
    measurements: list[AiMeasurement] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineRequest:
    dicom_path: Path
    output_dir: Path | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    dicom_path: Path
    status: str
    ai_result: AiResult | None = None
    error: str | None = None


@dataclass
class FileNode:
    path: Path
    is_dir: bool
    children: list[FileNode] = field(default_factory=list)
