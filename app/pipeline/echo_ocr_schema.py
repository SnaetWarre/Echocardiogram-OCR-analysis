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
    ocr_text_raw: str
    ocr_confidence: float
    parser_confidence: float
    roi_bbox: tuple[int, int, int, int]
    text_order: int = 0
    processed_at: str = ""
    pipeline_version: str = ""
    ocr_engine: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["roi_bbox"] = ",".join(str(value) for value in self.roi_bbox)
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
    "ocr_text_raw",
    "ocr_confidence",
    "parser_confidence",
    "roi_bbox",
    "text_order",
    "processed_at",
    "pipeline_version",
    "ocr_engine",
]
