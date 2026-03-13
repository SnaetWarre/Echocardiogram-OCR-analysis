from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class MeasurementRecord:
    study_uid: str
    series_uid: str
    sop_instance_uid: str
    frame_index: int
    measurement_name: str
    measurement_value: str
    measurement_unit: str
    exact_line_text: str
    line_confidence: float
    line_uncertain: bool
    ocr_text_raw: str
    ocr_confidence: float
    parser_confidence: float
    roi_bbox: tuple[int, int, int, int]
    line_bbox: tuple[int, int, int, int] | None = None
    text_order: int = 0
    processed_at: str = ""
    pipeline_version: str = ""
    ocr_engine: str = ""
    parser_source: str = ""
    source_kind: str = "pixel_ocr"
    source_path: str = ""
    source_modality: str = ""
    source_note: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["roi_bbox"] = ",".join(str(value) for value in self.roi_bbox)
        payload["line_bbox"] = "" if self.line_bbox is None else ",".join(str(value) for value in self.line_bbox)
        return payload

    @classmethod
    def now_iso(cls) -> str:
        return datetime.now(tz=timezone.utc).isoformat()


CSV_FIELDS = [
    "study_uid",
    "series_uid",
    "sop_instance_uid",
    "frame_index",
    "measurement_name",
    "measurement_value",
    "measurement_unit",
    "exact_line_text",
    "line_confidence",
    "line_uncertain",
    "ocr_text_raw",
    "ocr_confidence",
    "parser_confidence",
    "roi_bbox",
    "line_bbox",
    "text_order",
    "processed_at",
    "pipeline_version",
    "ocr_engine",
    "parser_source",
    "source_kind",
    "source_path",
    "source_modality",
    "source_note",
]
