from __future__ import annotations

from pathlib import Path

import numpy as np

from app.io.dicom_reader import read_dataset
from app.io.metadata_extractors import extract_metadata, extract_patient_info
from tests.io._helpers import write_dicom


def test_extract_patient_info_reads_known_fields(tmp_path: Path) -> None:
    path = write_dicom(tmp_path / "patient.dcm", np.full((1, 2, 2), 123, dtype=np.uint16))
    ds = read_dataset(path, load_pixels=False)
    patient = extract_patient_info(ds)

    assert patient.name == "Test"
    assert patient.patient_id is None


def test_extract_metadata_contains_core_properties(tmp_path: Path) -> None:
    path = write_dicom(tmp_path / "meta.dcm", np.full((3, 2, 2), 321, dtype=np.uint16))
    ds = read_dataset(path, load_pixels=False)
    metadata = extract_metadata(ds, path)

    assert metadata.path == path
    assert metadata.frame_count == 3
    assert metadata.rows == 2
    assert metadata.cols == 2
