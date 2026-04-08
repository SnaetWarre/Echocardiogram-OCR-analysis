from __future__ import annotations

from datetime import datetime

from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.output.echo_ocr_schema import MeasurementRecord


def test_ai_result_preserves_text_order() -> None:
    pipeline = EchoOcrPipeline()
    records = [
        MeasurementRecord(
            study_uid="s",
            series_uid="series",
            sop_instance_uid="sop",
            frame_index=0,
            measurement_name="LVEDV MOD BP",
            measurement_value="111.96",
            measurement_unit="ml",
            exact_line_text="2 LVEDV MOD BP 111.96 ml",
            line_confidence=0.9,
            line_uncertain=False,
            ocr_text_raw="",
            ocr_confidence=0.9,
            parser_confidence=0.9,
            roi_bbox=(0, 0, 10, 10),
            line_bbox=(0, 1, 10, 2),
            text_order=1,
            processed_at=datetime.now().isoformat(),
            pipeline_version="v1",
            ocr_engine="surya",
        ),
        MeasurementRecord(
            study_uid="s",
            series_uid="series",
            sop_instance_uid="sop",
            frame_index=0,
            measurement_name="EF Biplane",
            measurement_value="31.77",
            measurement_unit="%",
            exact_line_text="1 EF Biplane 31.77 %",
            line_confidence=0.9,
            line_uncertain=False,
            ocr_text_raw="",
            ocr_confidence=0.9,
            parser_confidence=0.9,
            roi_bbox=(0, 0, 10, 10),
            line_bbox=(0, 0, 10, 2),
            text_order=0,
            processed_at=datetime.now().isoformat(),
            pipeline_version="v1",
            ocr_engine="surya",
        ),
        MeasurementRecord(
            study_uid="s",
            series_uid="series",
            sop_instance_uid="sop",
            frame_index=0,
            measurement_name="LVESV MOD BP",
            measurement_value="76.40",
            measurement_unit="ml",
            exact_line_text="3 LVESV MOD BP 76.40 ml",
            line_confidence=0.9,
            line_uncertain=False,
            ocr_text_raw="",
            ocr_confidence=0.9,
            parser_confidence=0.9,
            roi_bbox=(0, 0, 10, 10),
            line_bbox=(0, 2, 10, 2),
            text_order=2,
            processed_at=datetime.now().isoformat(),
            pipeline_version="v1",
            ocr_engine="surya",
        ),
    ]

    result = pipeline._to_ai_result(records)

    assert [m.name for m in result.measurements] == [
        "EF Biplane",
        "LVEDV MOD BP",
        "LVESV MOD BP",
    ]
