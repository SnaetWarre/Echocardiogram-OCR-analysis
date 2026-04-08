from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.models.types import PipelineRequest
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.ocr.ocr_engines import OcrResult
from app.pipeline.measurements.study_companion_discovery import StudyCompanionDiscovery
from tests.io._helpers import write_dicom


def _write_sr(path: Path, *, study_uid: str) -> Path:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.Modality = "SR"
    ds.PatientName = "Test"
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID

    concept = Dataset()
    concept.CodeMeaning = "PV Vmax"

    units = Dataset()
    units.CodeMeaning = "m/s"
    units.CodeValue = "m/s"

    measured = Dataset()
    measured.NumericValue = "0.87"
    measured.MeasurementUnitsCodeSequence = Sequence([units])

    content = Dataset()
    content.ValueType = "NUM"
    content.ConceptNameCodeSequence = Sequence([concept])
    content.MeasuredValueSequence = Sequence([measured])

    ds.ContentSequence = Sequence([content])
    ds.save_as(str(path))
    return path


def test_study_companion_discovery_extracts_measurements_from_sr(tmp_path: Path) -> None:
    frames = np.zeros((1, 16, 16), dtype=np.uint16)
    us_path = write_dicom(tmp_path / "image.dcm", frames)

    from app.io.dicom_reader import read_dataset

    us_ds = read_dataset(us_path, load_pixels=False)
    _write_sr(tmp_path / "report.dcm", study_uid=str(us_ds.StudyInstanceUID))

    discovery = StudyCompanionDiscovery()
    result = discovery.discover(us_path, study_instance_uid=str(us_ds.StudyInstanceUID))

    assert result.has_measurements
    assert result.measurements[0].name == "PV Vmax"
    assert result.measurements[0].value == "0.87"
    assert result.measurements[0].unit == "m/s"


class _RecordingOcrEngine:
    name = "recording-ocr"

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, image) -> OcrResult:
        _ = image
        self.calls += 1
        return OcrResult(text="junk", confidence=0.1, tokens=[], engine_name=self.name)


def test_pipeline_prefers_study_companion_measurements_before_pixel_ocr(tmp_path: Path) -> None:
    frames = np.zeros((1, 16, 16), dtype=np.uint16)
    us_path = write_dicom(tmp_path / "image.dcm", frames)
    from app.io.dicom_reader import read_dataset

    us_ds = read_dataset(us_path, load_pixels=False)
    _write_sr(tmp_path / "report.dcm", study_uid=str(us_ds.StudyInstanceUID))

    ocr_engine = _RecordingOcrEngine()
    pipeline = EchoOcrPipeline(
        ocr_engine=ocr_engine,
        config=PipelineConfig.with_parameters({"study_companion_enabled": True}),
    )

    result = pipeline.run(PipelineRequest(dicom_path=us_path))

    assert result.status == "ok"
    assert result.ai_result is not None
    assert result.ai_result.measurements[0].name == "PV Vmax"
    assert result.ai_result.raw["study_companion_used"] is True
    assert result.ai_result.boxes == []
    assert ocr_engine.calls == 0


def test_to_ai_result_skips_roi_overlays_for_non_pixel_line_predictions() -> None:
    pipeline = EchoOcrPipeline()

    result = pipeline._to_ai_result(
        [],
        raw_line_predictions=[
            {
                "frame_index": 0,
                "order": 0,
                "text": "PV Vmax 0.87 m/s",
                "confidence": 0.99,
                "uncertain": False,
                "line_bbox": None,
                "roi_bbox": [0, 0, 0, 0],
                "ocr_engine": "study-companion",
                "parser_source": "study_companion_sr",
                "source_kind": "study_companion_sr",
                "source_path": "report.dcm",
                "source_modality": "SR",
            },
        ],
    )

    assert result.boxes == []
    assert result.raw["exact_lines"] == ["PV Vmax 0.87 m/s"]
