from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.io.dicom_loader import DicomLoadError, load_dicom_series
from tests.io._helpers import write_dicom


def test_load_series_lazy_multi_frame_returns_frames(tmp_path: Path) -> None:
    frames = np.stack(
        [
            np.full((4, 5), 100, dtype=np.uint16),
            np.full((4, 5), 500, dtype=np.uint16),
            np.full((4, 5), 900, dtype=np.uint16),
        ]
    )
    path = write_dicom(tmp_path / "multi.dcm", frames)
    series = load_dicom_series(path, load_pixels=False)

    assert series.frame_loader is not None
    assert series.frame_count == 3

    frame = series.get_frame(2)
    assert frame.shape == (4, 5)
    assert frame.dtype == np.uint8
    assert frame.max() == 255


def test_load_series_with_pixels_returns_uint8_and_count(tmp_path: Path) -> None:
    frames = np.stack(
        [
            np.full((3, 3), 50, dtype=np.uint16),
            np.full((3, 3), 150, dtype=np.uint16),
        ]
    )
    path = write_dicom(tmp_path / "with_pixels.dcm", frames)
    series = load_dicom_series(path, load_pixels=True)

    assert series.raw_frames is not None
    assert series.raw_frames.shape == (2, 3, 3)
    assert series.raw_frames.dtype == np.uint8
    assert series.frame_count == 2


def test_load_invalid_dicom_raises(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.dcm"
    bad_path.write_text("not a dicom", encoding="utf-8")

    with pytest.raises(DicomLoadError):
        load_dicom_series(bad_path)
