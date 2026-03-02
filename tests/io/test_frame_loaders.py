from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
from pydicom.errors import InvalidDicomError

from app.io import frame_loaders
from app.io.errors import DicomLoadError
from app.io.frame_loaders import build_lazy_frame_loader


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

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", fake_dcmread)

    loader = build_lazy_frame_loader(Path("/tmp/fake.dcm"), read_frame_only=True, cache_frames=True, get_frame_fn=fake_get_frame)
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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake2.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)
    frame0 = loader(0)
    frame1 = loader(1)

    assert calls["count"] == 1
    assert frame0.shape == (2, 2)
    assert frame1.shape == (2, 2)


def test_lazy_loader_reuses_dataset_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", fake_dcmread)

    loader = build_lazy_frame_loader(Path("/tmp/fake4.dcm"), read_frame_only=False, cache_frames=False, get_frame_fn=None)
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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake5.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)
    frame = loader(0)

    assert frame.shape == (2, 2)

    with pytest.raises(IndexError):
        loader(1)

    with pytest.raises(IndexError):
        loader(-1)


def test_lazy_loader_invalid_frame_count_defaults_to_single_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "NaN"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.full((2, 2), 9, dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake_badcount.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)
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

    def fake_get_frame(*_a, **_k):
        raise AssertionError("default_dicom_get_frame should not be used for single-frame data")

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake_single.dcm"), read_frame_only=True, cache_frames=True, get_frame_fn=fake_get_frame)
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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(
        Path("/tmp/fake_missing_get_frame.dcm"),
        read_frame_only=True,
        cache_frames=True,
    )
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

    def fake_get_frame(*_a, **_k):
        raise RuntimeError("decoder failed")

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake_frame_error.dcm"), read_frame_only=True, cache_frames=True, get_frame_fn=fake_get_frame)
    with pytest.raises(DicomLoadError):
        loader(0)


def test_lazy_loader_full_decode_out_of_range_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDS:
        NumberOfFrames = "2"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.stack(
                [np.full((2, 2), 10, dtype=np.uint16), np.full((2, 2), 20, dtype=np.uint16)]
            )

    ds = FakeDS()
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)
    loader = build_lazy_frame_loader(Path("/tmp/fake_oob.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)

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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)
    loader = build_lazy_frame_loader(
        Path("/tmp/fake_decode_fail.dcm"),
        read_frame_only=False,
        cache_frames=True,
    )

    with pytest.raises(DicomLoadError):
        loader(0)


def test_lazy_loader_dcmread_runtime_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_dcmread(*_a, **_k):
        raise RuntimeError("io failure")

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", fake_dcmread)
    loader = build_lazy_frame_loader(Path("/tmp/fake_runtime.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)

    with pytest.raises(DicomLoadError):
        loader(0)


def test_lazy_loader_dcmread_invalid_dicom_raises_dicom_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_dcmread(*_a, **_k):
        raise InvalidDicomError("bad")

    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", fake_dcmread)
    loader = build_lazy_frame_loader(Path("/tmp/fake_invalid.dcm"), read_frame_only=True, cache_frames=True, get_frame_fn=None)

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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(Path("/tmp/fake3.dcm"), read_frame_only=False, cache_frames=True, get_frame_fn=None)
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
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert not errors
    assert len(results) == 8
    expected_values = {63, 127, 191, 255}
    assert all(value in expected_values for value in results)
