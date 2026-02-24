from __future__ import annotations

from pathlib import Path

import numpy as np

from app.io.dicom_loader import load_dicom_series
from tests.io._helpers import write_dicom


def test_load_dicom_series_lazy_then_decode_frame(tmp_path: Path) -> None:
    path = write_dicom(
        tmp_path / "integration.dcm",
        np.stack([np.full((2, 2), 100, dtype=np.uint16), np.full((2, 2), 200, dtype=np.uint16)]),
    )
    series = load_dicom_series(path, load_pixels=False)

    assert series.raw_frames is None
    frame = series.get_frame(1)
    assert frame.shape == (2, 2)
    assert frame.dtype == np.uint8


def test_load_dicom_series_eager_pixels(tmp_path: Path) -> None:
    path = write_dicom(tmp_path / "integration_eager.dcm", np.full((1, 3, 3), 444, dtype=np.uint16))
    series = load_dicom_series(path, load_pixels=True)

    assert series.raw_frames is not None
    assert series.frame_count == 1
    assert series.get_frame(0).shape == (3, 3)
