from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.io import frame_loaders
from app.io.frame_loaders import build_lazy_frame_loader
from app.io.normalization import normalize_frames, to_uint8


def test_normalize_frames_scales_to_uint8() -> None:
    arr = np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)
    normalized = normalize_frames(arr)
    assert normalized.shape == (1, 2, 2)
    assert normalized.dtype == np.uint8
    assert normalized.max() == 255


def test_to_uint8_noop_for_uint8() -> None:
    arr = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    result = to_uint8(arr)
    assert result is arr


def test_lazy_loader_full_decode_normalizes_uint8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDS:
        NumberOfFrames = "1"

        @property
        def pixel_array(self) -> np.ndarray:
            return np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)

    ds = FakeDS()
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(
        Path("/tmp/fake_norm.dcm"),
        read_frame_only=False,
        cache_frames=True,
    )
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
    monkeypatch.setattr(frame_loaders.pydicom, "dcmread", lambda *_a, **_k: ds)

    loader = build_lazy_frame_loader(
        Path("/tmp/fake_nocache.dcm"),
        read_frame_only=False,
        cache_frames=False,
    )
    loader(0)
    loader(0)

    assert calls["count"] == 2
