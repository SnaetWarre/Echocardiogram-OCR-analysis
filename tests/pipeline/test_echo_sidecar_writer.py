from __future__ import annotations

from pathlib import Path

from app.pipeline.echo_ocr_schema import MeasurementRecord
from app.pipeline.echo_sidecar_writer import SidecarWriter


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
            ocr_text_raw="PV Vmax 0.87 m/s",
            ocr_confidence=0.91,
            parser_confidence=0.88,
            roi_bbox=(1, 2, 3, 4),
            processed_at=MeasurementRecord.now_iso(),
            pipeline_version="v1",
        )
    ]

    paths = writer.write("example", records)
    assert len(paths) == 2
    jsonl_path = tmp_path / "example.measurements.jsonl"
    csv_path = tmp_path / "example.measurements.csv"
    assert jsonl_path.exists()
    assert csv_path.exists()
