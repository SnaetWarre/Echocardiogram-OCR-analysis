from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import DicomMetadata
from app.pipeline.layout.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector


@dataclass(frozen=True)
class _ExamCandidate:
    path: Path
    frame_count: int
    metadata: DicomMetadata


@dataclass(frozen=True)
class _PreparedVideo:
    path: Path
    frame_count: int
    metadata: DicomMetadata
    frames: np.ndarray


_DEFAULT_ZOOM_CROP_FRACTIONS: tuple[float, ...] = (1.0, 0.92, 0.84, 0.76, 0.68, 0.6)


def discover_exam_video_candidates(
    measurement_path: Path,
    exam_root: Path | None = None,
) -> list[Path]:
    measurement = measurement_path.expanduser().resolve()
    root = _resolve_exam_root(measurement, exam_root)
    candidates: list[Path] = []
    for item in _cached_exam_candidates(str(root)):
        if item.path == measurement:
            continue
        if item.frame_count <= 1:
            continue
        candidates.append(item.path)
    return candidates


def build_matcher_scope_for_measurement_dicom(
    measurement_path: Path,
    exam_root: Path | None = None,
    *,
    max_edge: int = 320,
) -> dict[str, Any]:
    measurement = measurement_path.expanduser().resolve()
    measurement_series = load_dicom_series(measurement, load_pixels=False)
    if measurement_series.frame_count != 1:
        raise ValueError("Matcher scope preview only supports single-frame measurement DICOMs.")
    frame = _to_gray_frame(measurement_series.get_frame(0))
    mask = _build_query_mask(frame)
    target_shape = _scaled_shape(frame.shape, max_edge=max_edge)
    frame_scaled = _resize_nearest(frame, target_shape)
    mask_scaled = _resize_mask(mask, target_shape)
    return {
        "exam_root": str(_resolve_exam_root(measurement, exam_root)),
        "frame": frame,
        "mask": mask,
        "frame_scaled": frame_scaled,
        "mask_scaled": mask_scaled,
        "target_shape": target_shape,
    }


def rank_video_sources_for_measurement_dicom(
    measurement_path: Path,
    exam_root: Path | None = None,
    *,
    max_edge: int = 320,
    min_pearson: float = 0.72,
    min_margin: float = 0.015,
    frame_step: int = 1,
    zoom_crop_fractions: tuple[float, ...] | None = None,
) -> list[dict[str, Any]]:
    measurement = measurement_path.expanduser().resolve()
    measurement_series = load_dicom_series(measurement, load_pixels=False)
    if measurement_series.frame_count != 1:
        return []

    measurement_meta = measurement_series.metadata
    root = _resolve_exam_root(measurement, exam_root)
    candidate_entries = _filtered_exam_candidates(
        root=root,
        measurement_path=measurement,
        measurement_meta=measurement_meta,
    )
    if not candidate_entries:
        return []

    query_frame = _to_gray_frame(measurement_series.get_frame(0))
    mask = _build_query_mask(query_frame)
    target_shape = _scaled_shape(query_frame.shape, max_edge=max_edge)
    query_scaled = _resize_nearest(query_frame, target_shape)
    mask_scaled = _resize_mask(mask, target_shape)
    if int(mask_scaled.sum()) < 256:
        mask_scaled = np.ones(target_shape, dtype=bool)
    query_values = query_scaled.reshape(-1)[mask_scaled.reshape(-1)].astype(np.float32)

    ranked: list[dict[str, Any]] = []
    stride = max(1, int(frame_step))
    crop_fractions = _normalize_zoom_crop_fractions(zoom_crop_fractions)
    prepared_by_path = {
        prepared.path: prepared
        for prepared in _prepared_exam_videos(str(root), target_shape[0], target_shape[1])
    }
    for candidate in candidate_entries:
        prepared = prepared_by_path.get(candidate.path)
        if prepared is None:
            continue
        best_frame_index, best_score, best_mae, best_crop_fraction = _best_frame_match(
            prepared.frames,
            query_values,
            mask_scaled.reshape(-1),
            stride=stride,
            crop_fractions=crop_fractions,
        )
        ranked.append(
            {
                "dicomid": str(candidate.path),
                "frame": int(best_frame_index),
                "score": float(best_score),
                "mae": float(best_mae),
                "crop_fraction": float(best_crop_fraction),
                "zoom_factor": float(1.0 / best_crop_fraction),
                "matched": bool(best_score >= min_pearson),
                "reason": "",
            }
        )

    ranked.sort(key=lambda item: (-float(item["score"]), float(item["mae"]), str(item["dicomid"])))
    if ranked:
        ranked[0]["matched"] = bool(ranked[0]["score"] >= min_pearson)
        ranked[0]["reason"] = _top_match_reason(ranked, min_pearson=min_pearson, min_margin=min_margin)
    for entry in ranked[1:]:
        entry["matched"] = False
        entry["reason"] = "not_top_ranked"
    return ranked


def find_source_video_for_measurement_dicom(
    measurement_path: Path,
    exam_root: Path | None = None,
    *,
    max_edge: int = 320,
    min_pearson: float = 0.72,
    min_margin: float = 0.015,
    frame_step: int = 1,
    zoom_crop_fractions: tuple[float, ...] | None = None,
) -> dict[str, Any]:
    ranked = rank_video_sources_for_measurement_dicom(
        measurement_path,
        exam_root,
        max_edge=max_edge,
        min_pearson=min_pearson,
        min_margin=min_margin,
        frame_step=frame_step,
        zoom_crop_fractions=zoom_crop_fractions,
    )
    if not ranked:
        return {
            "dicomid": None,
            "frame": None,
            "score": None,
            "mae": None,
            "crop_fraction": None,
            "zoom_factor": None,
            "matched": False,
            "reason": "no_video_candidates",
        }

    best = dict(ranked[0])
    if str(best.get("reason", "")).strip():
        best["matched"] = False
    if not bool(best.get("matched")):
        best["dicomid"] = None
        best["frame"] = None
    return best


def _resolve_exam_root(measurement_path: Path, exam_root: Path | None) -> Path:
    root = exam_root or measurement_path.parent
    return root.expanduser().resolve()


@lru_cache(maxsize=128)
def _cached_exam_candidates(exam_root: str) -> tuple[_ExamCandidate, ...]:
    root = Path(exam_root)
    items: list[_ExamCandidate] = []
    for path in sorted(root.glob("*.dcm")):
        series = load_dicom_series(path, load_pixels=False)
        items.append(
            _ExamCandidate(
                path=path.resolve(),
                frame_count=series.frame_count,
                metadata=series.metadata,
            )
        )
    return tuple(items)


def _filtered_exam_candidates(
    *,
    root: Path,
    measurement_path: Path,
    measurement_meta: DicomMetadata,
) -> list[_ExamCandidate]:
    exact_shape: list[_ExamCandidate] = []
    fallback_shape: list[_ExamCandidate] = []
    for item in _cached_exam_candidates(str(root)):
        if item.path == measurement_path or item.frame_count <= 1:
            continue
        if not _compatible_dimensions(measurement_meta, item.metadata):
            continue
        if _same_study(measurement_meta, item.metadata):
            exact_shape.append(item)
        else:
            fallback_shape.append(item)
    return exact_shape or fallback_shape


@lru_cache(maxsize=32)
def _prepared_exam_videos(
    exam_root: str,
    target_h: int,
    target_w: int,
) -> tuple[_PreparedVideo, ...]:
    shape = (int(target_h), int(target_w))
    prepared: list[_PreparedVideo] = []
    for item in _cached_exam_candidates(exam_root):
        if item.frame_count <= 1:
            continue
        series = load_dicom_series(item.path, load_pixels=False)
        frames = np.stack(
            [_resize_nearest(_to_gray_frame(series.get_frame(index)), shape) for index in range(series.frame_count)],
            axis=0,
        )
        prepared.append(
            _PreparedVideo(
                path=item.path,
                frame_count=item.frame_count,
                metadata=item.metadata,
                frames=frames.astype(np.uint8, copy=False),
            )
        )
    return tuple(prepared)


def _same_study(a: DicomMetadata, b: DicomMetadata) -> bool:
    if a.study_instance_uid and b.study_instance_uid:
        return str(a.study_instance_uid) == str(b.study_instance_uid)
    return True


def _compatible_dimensions(a: DicomMetadata, b: DicomMetadata) -> bool:
    if a.rows and b.rows and int(a.rows) != int(b.rows):
        return False
    if a.cols and b.cols and int(a.cols) != int(b.cols):
        return False
    return True


def _to_gray_frame(frame: np.ndarray) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.ndim == 2:
        return arr.astype(np.uint8, copy=False)
    if arr.ndim == 3 and arr.shape[-1] >= 3:
        rgb = arr[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {arr.shape}")


def _build_query_mask(frame: np.ndarray) -> np.ndarray:
    center_mask = _central_crop_mask(frame.shape[:2], margin_fraction=0.25)
    detector = TopLeftBlueGrayBoxDetector()
    detection = detector.detect(frame)
    if detection.present and detection.bbox is not None:
        h, w = frame.shape[:2]
        x, y, bw, bh = detection.bbox
        pad = 8
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w, x + bw + pad)
        y2 = min(h, y + bh + pad)
        mask = center_mask.copy()
        mask[y1:y2, x1:x2] = False
        if int(mask.sum()) >= 256:
            return mask
    return center_mask


def _central_crop_mask(shape: tuple[int, int], *, margin_fraction: float) -> np.ndarray:
    h, w = shape
    margin_y = max(0, int(round(h * margin_fraction)))
    margin_x = max(0, int(round(w * margin_fraction)))
    top = min(margin_y, max(0, h - 1))
    left = min(margin_x, max(0, w - 1))
    bottom = max(top + 1, h - margin_y)
    right = max(left + 1, w - margin_x)
    mask = np.zeros((h, w), dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


def _scaled_shape(shape: tuple[int, int], *, max_edge: int) -> tuple[int, int]:
    h, w = shape
    longest = max(h, w)
    if longest <= max_edge:
        return (h, w)
    scale = float(max_edge) / float(longest)
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))
    return (new_h, new_w)


def _resize_nearest(image: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    src_h, src_w = image.shape[:2]
    dst_h, dst_w = shape
    if (src_h, src_w) == (dst_h, dst_w):
        return image.astype(np.uint8, copy=False)
    y_idx = np.clip(np.round(np.linspace(0, src_h - 1, dst_h)).astype(int), 0, src_h - 1)
    x_idx = np.clip(np.round(np.linspace(0, src_w - 1, dst_w)).astype(int), 0, src_w - 1)
    return image[np.ix_(y_idx, x_idx)].astype(np.uint8, copy=False)


def _resize_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    scaled = _resize_nearest(mask.astype(np.uint8) * 255, shape)
    return scaled >= 128


def _best_frame_match(
    candidate_frames: np.ndarray,
    query_values: np.ndarray,
    mask_flat: np.ndarray,
    *,
    stride: int,
    crop_fractions: tuple[float, ...],
) -> tuple[int, float, float, float]:
    if candidate_frames.ndim != 3:
        raise ValueError(f"Expected candidate frame stack (N, H, W), got {candidate_frames.shape}")
    frame_indices = np.arange(candidate_frames.shape[0], dtype=int)[::stride]
    frames = candidate_frames[::stride]
    best_frame_index = -1
    best_score = float("-inf")
    best_mae = float("inf")
    best_crop_fraction = 1.0

    for pos, frame in enumerate(frames):
        for crop_fraction in crop_fractions:
            candidate_view = _resize_nearest(_center_crop(frame, crop_fraction=crop_fraction), frame.shape)
            pixels = candidate_view.reshape(-1)[mask_flat].astype(np.float32, copy=False)
            score = _pearson_from_values(pixels, query_values)
            mae = float(np.mean(np.abs(pixels - query_values)) / 255.0)
            if (
                score > best_score
                or (score == best_score and mae < best_mae)
                or (score == best_score and mae == best_mae and crop_fraction > best_crop_fraction)
            ):
                best_frame_index = int(frame_indices[pos])
                best_score = float(score)
                best_mae = float(mae)
                best_crop_fraction = float(crop_fraction)

    return best_frame_index, best_score, best_mae, best_crop_fraction


def _normalize_zoom_crop_fractions(
    crop_fractions: tuple[float, ...] | None,
) -> tuple[float, ...]:
    values = crop_fractions or _DEFAULT_ZOOM_CROP_FRACTIONS
    cleaned = sorted(
        {
            float(value)
            for value in values
            if isinstance(value, (int, float)) and 0.0 < float(value) <= 1.0
        },
        reverse=True,
    )
    return tuple(cleaned) if cleaned else (1.0,)


def _center_crop(frame: np.ndarray, *, crop_fraction: float) -> np.ndarray:
    if crop_fraction >= 0.999:
        return frame
    h, w = frame.shape[:2]
    crop_h = max(1, min(h, int(round(h * crop_fraction))))
    crop_w = max(1, min(w, int(round(w * crop_fraction))))
    top = max(0, (h - crop_h) // 2)
    left = max(0, (w - crop_w) // 2)
    bottom = min(h, top + crop_h)
    right = min(w, left + crop_w)
    return frame[top:bottom, left:right]


def _pearson_from_values(candidate_values: np.ndarray, query_values: np.ndarray) -> float:
    query_centered = query_values - float(query_values.mean())
    query_norm = float(np.linalg.norm(query_centered))
    if query_norm <= 1e-9:
        return 1.0 if np.array_equal(candidate_values, query_values) else 0.0

    centered = candidate_values - float(candidate_values.mean())
    norm = float(np.linalg.norm(centered))
    denom = norm * query_norm
    if denom <= 1e-9:
        return 1.0 if np.array_equal(candidate_values, query_values) else 0.0
    return float(np.dot(centered, query_centered) / denom)


def _pearson_correlation(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    a_vals = a[mask].astype(np.float32)
    b_vals = b[mask].astype(np.float32)
    if a_vals.size == 0 or b_vals.size == 0:
        return -1.0
    a_centered = a_vals - float(a_vals.mean())
    b_centered = b_vals - float(b_vals.mean())
    denom = float(np.linalg.norm(a_centered) * np.linalg.norm(b_centered))
    if denom <= 1e-9:
        return 1.0 if np.array_equal(a_vals, b_vals) else 0.0
    return float(np.clip(np.dot(a_centered, b_centered) / denom, -1.0, 1.0))


def _normalized_mae(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    a_vals = a[mask].astype(np.float32)
    b_vals = b[mask].astype(np.float32)
    if a_vals.size == 0 or b_vals.size == 0:
        return 1.0
    return float(np.mean(np.abs(a_vals - b_vals)) / 255.0)


def _top_match_reason(
    ranked: list[dict[str, Any]],
    *,
    min_pearson: float,
    min_margin: float,
) -> str:
    top = ranked[0]
    top_score = float(top.get("score", 0.0) or 0.0)
    if top_score < min_pearson:
        return "score_below_threshold"
    if len(ranked) >= 2:
        runner_up = float(ranked[1].get("score", 0.0) or 0.0)
        if (top_score - runner_up) < min_margin:
            return "ambiguous_top_match"
    return ""
