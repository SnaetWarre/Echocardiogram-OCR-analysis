from __future__ import annotations

from pathlib import Path

import numpy as np

from app.io.video_source_matcher import (
    build_matcher_scope_for_measurement_dicom,
    discover_exam_video_candidates,
    find_source_video_for_measurement_dicom,
    rank_video_sources_for_measurement_dicom,
)
from app.io import video_source_matcher
from tests.io._helpers import write_dicom


def _base_frame(seed: int, *, shape: tuple[int, int] = (72, 96)) -> np.ndarray:
    y = np.linspace(0.0, 1.0, shape[0], dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, shape[1], dtype=np.float32)[None, :]
    frame = ((seed * 17.0) + y * 130.0 + x * 90.0) % 255.0
    return frame.astype(np.uint16)


def _video_frames(count: int) -> np.ndarray:
    return np.stack([_base_frame(index + 1) for index in range(count)], axis=0)


def _textured_video_frames(count: int, *, shape: tuple[int, int] = (72, 96)) -> np.ndarray:
    frames: list[np.ndarray] = []
    yy, xx = np.indices(shape)
    for index in range(count):
        rng = np.random.default_rng(100 + index)
        base = rng.integers(0, 256, size=shape, dtype=np.uint16)
        cx = 18 + index * 9
        cy = 16 + index * 7
        radius = 10 + index
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
        frame = base.copy()
        frame[mask] = np.uint16((40 + index * 35) % 256)
        frames.append(frame)
    return np.stack(frames, axis=0)


def _overlay_corner_box(frame: np.ndarray, *, value: int = 0) -> np.ndarray:
    out = frame.copy()
    out[:12, :20] = np.uint16(value)
    return out


def _zoom_center(frame: np.ndarray, *, crop_fraction: float) -> np.ndarray:
    h, w = frame.shape[:2]
    crop_h = max(1, min(h, int(round(h * crop_fraction))))
    crop_w = max(1, min(w, int(round(w * crop_fraction))))
    top = max(0, (h - crop_h) // 2)
    left = max(0, (w - crop_w) // 2)
    bottom = min(h, top + crop_h)
    right = min(w, left + crop_w)
    cropped = frame[top:bottom, left:right]
    y_idx = np.clip(np.round(np.linspace(0, cropped.shape[0] - 1, h)).astype(int), 0, cropped.shape[0] - 1)
    x_idx = np.clip(np.round(np.linspace(0, cropped.shape[1] - 1, w)).astype(int), 0, cropped.shape[1] - 1)
    return cropped[np.ix_(y_idx, x_idx)].astype(frame.dtype, copy=False)


def test_discover_exam_video_candidates_only_returns_multiframe_siblings(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    measurement = write_dicom(exam / "measurement.dcm", _base_frame(3))
    write_dicom(exam / "cine_a.dcm", _video_frames(3))
    write_dicom(exam / "cine_b.dcm", _video_frames(4))
    write_dicom(exam / "other_image.dcm", _base_frame(6))

    candidates = discover_exam_video_candidates(measurement)

    assert [path.name for path in candidates] == ["cine_a.dcm", "cine_b.dcm"]


def test_find_source_video_returns_exact_matching_video_and_frame(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    video = _video_frames(5)
    write_dicom(exam / "video.dcm", video)
    measurement = write_dicom(exam / "measurement.dcm", video[2])

    match = find_source_video_for_measurement_dicom(measurement)

    assert match["matched"] is True
    assert Path(str(match["dicomid"])).name == "video.dcm"
    assert match["frame"] == 2
    assert float(match["zoom_factor"]) == 1.0


def test_find_source_video_handles_measurement_overlay_using_central_crop(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    video = _video_frames(4)
    write_dicom(exam / "video.dcm", video)
    measurement = write_dicom(exam / "measurement.dcm", _overlay_corner_box(video[1], value=255))

    match = find_source_video_for_measurement_dicom(measurement, min_pearson=0.3)

    assert match["matched"] is True
    assert Path(str(match["dicomid"])).name == "video.dcm"
    assert match["frame"] == 1


def test_find_source_video_handles_center_zoomed_measurement(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    rng = np.random.default_rng(42)
    video = rng.integers(0, 256, size=(4, 72, 96), dtype=np.uint16)
    write_dicom(exam / "video.dcm", video)
    write_dicom(exam / "distractor.dcm", rng.integers(0, 256, size=(4, 72, 96), dtype=np.uint16))
    measurement = write_dicom(exam / "measurement.dcm", _zoom_center(video[2], crop_fraction=0.68))

    match = find_source_video_for_measurement_dicom(measurement, min_pearson=0.5)

    assert match["matched"] is True
    assert Path(str(match["dicomid"])).name == "video.dcm"
    assert match["frame"] == 2
    assert float(match["zoom_factor"]) > 1.3


def test_rank_video_sources_prefers_contrast_shifted_true_parent(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    video = _textured_video_frames(5)
    write_dicom(exam / "video.dcm", video)
    distractor = np.stack([np.flipud(frame) for frame in video], axis=0)
    write_dicom(exam / "distractor.dcm", distractor)
    contrast_shifted = np.clip(video[3].astype(np.int32) + 25, 0, 255).astype(np.uint16)
    measurement = write_dicom(exam / "measurement.dcm", contrast_shifted)

    ranked = rank_video_sources_for_measurement_dicom(measurement, min_pearson=0.2)

    assert ranked
    assert Path(str(ranked[0]["dicomid"])).name == "video.dcm"
    assert ranked[0]["frame"] == 3
    assert float(ranked[0]["score"]) > float(ranked[1]["score"])


def test_find_source_video_rejects_weak_match(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    write_dicom(exam / "video.dcm", _video_frames(4))
    noise = np.random.default_rng(7).integers(0, 256, size=(72, 96), dtype=np.uint16)
    measurement = write_dicom(exam / "measurement.dcm", noise)

    match = find_source_video_for_measurement_dicom(measurement, min_pearson=0.95)

    assert match["matched"] is False
    assert match["dicomid"] is None
    assert match["frame"] is None
    assert match["reason"] == "score_below_threshold"


def test_exam_video_cache_reuses_decoded_candidates_across_measurement_queries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    video = _video_frames(5)
    video_path = write_dicom(exam / "video.dcm", video)
    measurement_a = write_dicom(exam / "measurement_a.dcm", video[1])
    measurement_b = write_dicom(exam / "measurement_b.dcm", video[3])
    load_counts: dict[str, int] = {}
    original = video_source_matcher.load_dicom_series

    def _counting_loader(path: Path, *args: object, **kwargs: object):
        key = path.name
        load_counts[key] = load_counts.get(key, 0) + 1
        return original(path, *args, **kwargs)

    video_source_matcher._cached_exam_candidates.cache_clear()
    video_source_matcher._prepared_exam_videos.cache_clear()
    monkeypatch.setattr(video_source_matcher, "load_dicom_series", _counting_loader)

    first = find_source_video_for_measurement_dicom(measurement_a)
    second = find_source_video_for_measurement_dicom(measurement_b)

    assert first["matched"] is True
    assert second["matched"] is True
    assert load_counts[video_path.name] == 2


def test_build_matcher_scope_uses_ultrasound_sector_window(tmp_path: Path) -> None:
    exam = tmp_path / "patient" / "exam"
    exam.mkdir(parents=True)
    measurement = write_dicom(exam / "measurement.dcm", _base_frame(3, shape=(80, 100)))

    scope = build_matcher_scope_for_measurement_dicom(measurement, max_edge=100)

    mask = scope["mask"]
    assert mask.shape == (80, 100)
    assert bool(mask[8, 50]) is True
    assert bool(mask[20, 50]) is True
    assert bool(mask[60, 50]) is True
    assert bool(mask[70, 50]) is False
    assert bool(mask[20, 25]) is False
    assert bool(mask[20, 75]) is False
    assert bool(mask[79, 5]) is False
    assert bool(mask[79, 95]) is False
