from __future__ import annotations

import csv
import json
from pathlib import Path

from app.pipeline.output.echo_ocr_schema import MeasurementRecord
from app.pipeline.output.echo_sidecar_writer import SidecarWriter


def test_sidecar_writer_writes_jsonl_and_csv(tmp_path: Path) -> None:
    writer = SidecarWriter(output_dir=tmp_path)
    records = [
        MeasurementRecord(
            study_uid="study-1",
            series_uid="series-1",
            sop_instance_uid="sop-1",
            frame_index=3,
            measurement_name="PV Vmax",
            measurement_value="0.87",
            measurement_unit="m/s",
            exact_line_text="PV Vmax 0.87 m/s",
            line_confidence=0.91,
            line_uncertain=False,
            ocr_text_raw="PV Vmax 0.87 m/s",
            ocr_confidence=0.91,
            parser_confidence=0.88,
            roi_bbox=(1, 2, 3, 4),
            line_bbox=(5, 6, 7, 8),
            processed_at=MeasurementRecord.now_iso(),
            pipeline_version="v1",
            ocr_engine="easyocr",
        )
    ]

    paths = writer.write("example", records)
    assert len(paths) == 2
    jsonl_path = tmp_path / "example.measurements.jsonl"
    csv_path = tmp_path / "example.measurements.csv"
    assert jsonl_path.exists()
    assert csv_path.exists()

    json_row = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])
    assert json_row["measurement_name"] == "PV Vmax"
    assert json_row["measurement_value"] == "0.87"
    assert json_row["exact_line_text"] == "PV Vmax 0.87 m/s"
    assert json_row["ocr_engine"] == "easyocr"
    assert json_row["roi_bbox"] == "1,2,3,4"
    assert json_row["line_bbox"] == "5,6,7,8"

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_row = next(csv.DictReader(handle))
    assert csv_row["measurement_name"] == "PV Vmax"
    assert csv_row["measurement_value"] == "0.87"
    assert csv_row["exact_line_text"] == "PV Vmax 0.87 m/s"
    assert csv_row["ocr_engine"] == "easyocr"
    assert csv_row["roi_bbox"] == "1,2,3,4"
    assert csv_row["line_bbox"] == "5,6,7,8"
