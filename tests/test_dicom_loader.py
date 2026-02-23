from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np
import pytest

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.errors import InvalidDicomError
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io import dicom_loader
from app.io.dicom_loader import (  # noqa: E402
    DicomLoadError,
    build_lazy_frame_loader,
    load_dicom_series,
)


def _write_dicom(path: Path, frames: np.ndarray) -> Path:
    if frames.ndim == 2:
        frames = frames[np.newaxis, ...]
    if frames.ndim != 3:
        raise ValueError("frames must be 2D or 3D (N, H, W)")

    num_frames, rows, cols = frames.shape

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.PatientName = "Test"
    ds.Rows = rows
    ds.Columns = cols
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0

    if num_frames > 1:
        ds.NumberOfFrames = str(num_frames)

    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.PixelData = frames.astype(np.uint16).tobytes()
    ds.save_as(str(path))
    return path


def test_lazy_loader_uses_get_frame_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDS:
        NumberOfFrames = "3"

        @property
        def pixel_array(self) -> np.ndarray:
            raise AssertionError("pixel_array should not be accessed in frame-only mode")

    ds = FakeDS()

    def fake_dcmread(*_args, **_kwargs):
        return ds

    def fake_get_frame(dataset, index: int) -> np.ndarray:
        assert dataset is ds
        base = np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)
        return base + index

    monkeypatch.setattr(dicom_loader, "dicom_get_frame", fake_get_frame)
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)

    loader = build_lazy_frame_loader(Path("/tmp/fake.dcm"), read_frame_only=True, cache_frames=True)
    frame = loader(1)

    assert frame.shape == (2, 2)
    assert frame.dtype == np.uint8
    assert frame.max() == 255

    with pytest.raises(IndexError):
        loader(5)


def test_lazy_loader_caches_full_decode_when_frame_only_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    class FakeDS:
        NumberOfFrames = "2"

        @property
        def pixel_array(self) -> np.ndarray:
            calls["count"] += 1
            return np.stack(
                [
                    np.full((2, 2), 10, dtype=np.uint16),
                    np.full((2, 2), 20, dtype=np.uint16),
                ]
            )

    ds = FakeDS()

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake2.dcm"), read_frame_only=False, cache_frames=True)
    frame0 = loader(0)
    frame1 = loader(1)

    assert calls["count"] == 1
    assert frame0.shape == (2, 2)
    assert frame1.shape == (2, 2)


def test_load_series_lazy_multi_frame_returns_frames(tmp_path: Path) -> None:
    frames = np.stack(
        [
            np.full((4, 5), 100, dtype=np.uint16),
            np.full((4, 5), 500, dtype=np.uint16),
            np.full((4, 5), 900, dtype=np.uint16),
        ]
    )
    path = _write_dicom(tmp_path / "multi.dcm", frames)
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
    path = _write_dicom(tmp_path / "with_pixels.dcm", frames)
    series = load_dicom_series(path, load_pixels=True)

    assert series.raw_frames is not None
    assert series.raw_frames.shape == (2, 3, 3)
    assert series.raw_frames.dtype == np.uint8
    assert series.frame_count == 2

def test_lazy_loader_reuses_dataset_between_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.full((2, 2), 123, dtype=np.uint16)

    ds = FakeDS()

    def fake_dcmread(*_a, **_k):
        calls["count"] += 1
        return ds

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake4.dcm"), read_frame_only=False, cache_frames=False)
    frame0 = loader(0)
    frame1 = loader(0)

    assert calls["count"] == 1
    assert frame0.shape == (2, 2)
    assert frame1.shape == (2, 2)


def test_lazy_loader_treats_non_positive_frame_count_as_single_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "0"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.full((2, 2), 42, dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake5.dcm"), read_frame_only=False, cache_frames=True)
    frame = loader(0)

    assert frame.shape == (2, 2)

    with pytest.raises(IndexError):
        loader(1)

    with pytest.raises(IndexError):
        loader(-1)


def test_lazy_loader_full_decode_normalizes_uint8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_norm.dcm"), read_frame_only=False, cache_frames=True)
    frame = loader(0)

    assert frame.dtype == np.uint8
    assert frame.max() == 255


def test_lazy_loader_full_decode_no_cache_redecodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            calls["count"] += 1
            return np.full((2, 2), 500, dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_nocache.dcm"), read_frame_only=False, cache_frames=False)
    loader(0)
    loader(0)

    assert calls["count"] == 2


def test_lazy_loader_invalid_frame_count_defaults_to_single_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "NaN"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.full((2, 2), 9, dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_badcount.dcm"), read_frame_only=False, cache_frames=True)
    frame = loader(0)

    assert frame.shape == (2, 2)

    with pytest.raises(IndexError):
        loader(1)


def test_lazy_loader_frame_only_uses_pixel_array_for_single_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.full((2, 2), 7, dtype=np.uint16)

    ds = FakeDS()

    def fake_dcmread(*_a, **_k):
        return ds

    def fake_get_frame(*_a, **_k):
        raise AssertionError("dicom_get_frame should not be used for single-frame data")

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", fake_get_frame)

    loader = build_lazy_frame_loader(Path("/tmp/fake_single.dcm"), read_frame_only=True, cache_frames=True)
    frame = loader(0)

    assert frame.shape == (2, 2)
    assert frame.dtype == np.uint8

def test_lazy_loader_frame_only_fallback_when_get_frame_missing_multi_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    class FakeDS:
        NumberOfFrames = "2"

        @property
        def pixel_array(self) -> np.ndarray:
            calls["count"] += 1
            return np.stack(
                [
                    np.full((2, 2), 100, dtype=np.uint16),
                    np.full((2, 2), 200, dtype=np.uint16),
                ]
            )

    ds = FakeDS()

    def fake_dcmread(*_a, **_k):
        return ds

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_missing_get_frame.dcm"), read_frame_only=True, cache_frames=True)
    frame0 = loader(0)
    frame1 = loader(1)

    assert calls["count"] == 2
    assert frame0.shape == (2, 2)
    assert frame1.shape == (2, 2)

def test_lazy_loader_frame_only_get_frame_error_surfaces_as_dicom_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "2"

        @property
        def pixel_array(self) -> np.ndarray:
            raise AssertionError("pixel_array should not be used in frame-only mode for multi-frame")

    ds = FakeDS()

    def fake_dcmread(*_a, **_k):
        return ds

    def fake_get_frame(*_a, **_k):
        raise RuntimeError("decoder failed")

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", fake_get_frame)

    loader = build_lazy_frame_loader(Path("/tmp/fake_frame_error.dcm"), read_frame_only=True, cache_frames=True)

    with pytest.raises(DicomLoadError):
        loader(0)


def test_lazy_loader_full_decode_out_of_range_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "2"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.stack(
                [
                    np.full((2, 2), 10, dtype=np.uint16),
                    np.full((2, 2), 20, dtype=np.uint16),
                ]
            )

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_oob.dcm"), read_frame_only=False, cache_frames=True)

    with pytest.raises(IndexError):
        loader(2)

def test_lazy_loader_full_decode_pixel_array_error_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            raise ValueError("decode failed")

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake_decode_fail.dcm"), read_frame_only=False, cache_frames=True)

    with pytest.raises(DicomLoadError):
        loader(0)

def test_lazy_loader_dcmread_runtime_error_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_dcmread(*_a, **_k):
        raise RuntimeError("io failure")

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)

    loader = build_lazy_frame_loader(Path("/tmp/fake_runtime.dcm"), read_frame_only=False, cache_frames=True)

    with pytest.raises(DicomLoadError):
        loader(0)

def test_lazy_loader_dcmread_invalid_dicom_raises_dicom_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_dcmread(*_a, **_k):
        raise InvalidDicomError("bad")

    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", fake_dcmread)

    loader = build_lazy_frame_loader(Path("/tmp/fake_invalid.dcm"), read_frame_only=True, cache_frames=True)

    with pytest.raises(DicomLoadError):
        loader(0)


def test_lazy_loader_thread_safety_under_concurrent_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "4"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.stack(
                [
                    np.full((2, 2), 100, dtype=np.uint16),
                    np.full((2, 2), 200, dtype=np.uint16),
                    np.full((2, 2), 300, dtype=np.uint16),
                    np.full((2, 2), 400, dtype=np.uint16),
                ]
            )

    ds = FakeDS()
    monkeypatch.setattr(dicom_loader.pydicom, "dcmread", lambda *_a, **_k: ds)
    monkeypatch.setattr(dicom_loader, "dicom_get_frame", None)

    loader = build_lazy_frame_loader(Path("/tmp/fake3.dcm"), read_frame_only=False, cache_frames=True)

    barrier = threading.Barrier(8)
    errors: list[Exception] = []
    results: list[int] = []

    def _worker(index: int) -> None:
        try:
            barrier.wait(timeout=2)
            frame = loader(index)
            results.append(int(frame[0, 0]))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i % 4,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    assert not errors
    assert len(results) == 8
    expected_values = {63, 127, 191, 255}
    assert all(value in expected_values for value in results)


def test_load_invalid_dicom_raises(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.dcm"
    bad_path.write_text("not a dicom", encoding="utf-8")

    with pytest.raises(DicomLoadError):
        load_dicom_series(bad_path)
