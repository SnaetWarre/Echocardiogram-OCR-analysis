from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.ocr.preprocessing import preprocess_gray_x3_lanczos


@dataclass(frozen=True)
class CharSlice:
    x: int
    y: int
    width: int
    height: int
    ink_density: float
    local_ink_top: int = 0
    local_ink_bottom: int = 0


@dataclass(frozen=True)
class VerticalSliceResult:
    preprocessed_line: np.ndarray
    binary_mask: np.ndarray
    slices: tuple[CharSlice, ...]
    expected_char_count: int
    confidence: float
    reliable: bool
    gap_count: int
    gap_widths: tuple[int, ...]
    space_after: tuple[bool, ...]
    space_gap_threshold_px: int
    cut_columns: tuple[int, ...]
    unreliable_reason: str = ""


def _binarize_white_text_on_black(preprocessed_gray: np.ndarray) -> np.ndarray:
    if preprocessed_gray.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)

    gray = preprocessed_gray
    if gray.ndim == 3 and gray.shape[-1] >= 3:
        gray = cv2.cvtColor(gray[..., :3].astype(np.uint8, copy=False), cv2.COLOR_BGR2GRAY)
    elif gray.ndim == 3 and gray.shape[-1] == 1:
        gray = gray[..., 0]
    gray = gray.astype(np.uint8, copy=False)

    _threshold, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if float((binary > 0).mean()) > 0.5:
        binary = cv2.bitwise_not(binary)
    return binary


def _coarse_blob_reason(slices: tuple[CharSlice, ...], *, line_width: int, line_height: int) -> str:
    if not slices or line_width <= 0 or line_height <= 0:
        return "no_slices"

    widths = np.asarray([float(s.width) for s in slices], dtype=np.float32)
    gap_widths = np.asarray(
        [
            max(0.0, float(slices[idx].x - (slices[idx - 1].x + slices[idx - 1].width)))
            for idx in range(1, len(slices))
        ],
        dtype=np.float32,
    )
    coverage_ratio = float(widths.sum() / max(1.0, float(line_width)))
    mean_width = float(widths.mean())
    max_width = float(widths.max())
    width_height_ratio = mean_width / max(1.0, float(line_height))
    max_width_ratio = max_width / max(1.0, float(line_width))

    if len(slices) == 1 and max_width_ratio >= 0.35:
        return "single_wide_blob"
    if len(slices) <= 4 and coverage_ratio >= 0.72 and width_height_ratio >= 0.6:
        return "few_coarse_blobs"
    if gap_widths.size and width_height_ratio <= 0.12 and float(gap_widths.max() / max(1.0, mean_width)) >= 8.0:
        return "sparse_noise_runs"
    return ""


def _space_threshold_px(
    slices: tuple[CharSlice, ...],
    gap_widths: tuple[int, ...],
    *,
    min_space_gap_px: int,
    space_gap_ratio: float,
) -> int:
    if not slices:
        return int(max(1, min_space_gap_px))
    widths = np.asarray([max(1, s.width) for s in slices], dtype=np.float32)
    median_width = float(np.median(widths)) if widths.size else 0.0
    positive_gaps = np.asarray([gap for gap in gap_widths if gap > 0], dtype=np.float32)
    median_gap = float(np.median(positive_gaps)) if positive_gaps.size else 0.0
    threshold = max(
        float(min_space_gap_px),
        median_width * float(space_gap_ratio),
        median_gap * 1.5,
    )
    return int(max(1, round(threshold)))


def slice_line_into_vertical_slices(
    line_image: np.ndarray,
    *,
    max_gap_ink_px: int = 0,
    min_slice_width_px: int = 2,
    min_slice_height_px: int = 3,
    min_ink_ratio: float = 0.03,
    min_ink_pixels_px: int = 18,
    strong_column_ink_px: int = 3,
    min_strong_columns_px: int = 3,
    min_space_gap_px: int = 6,
    space_gap_ratio: float = 0.55,
) -> VerticalSliceResult:
    preprocessed_line = preprocess_gray_x3_lanczos(line_image)
    if preprocessed_line.size == 0:
        empty = np.zeros((0, 0), dtype=np.uint8)
        return VerticalSliceResult(
            preprocessed_line=empty,
            binary_mask=empty,
            slices=(),
            expected_char_count=0,
            confidence=0.0,
            reliable=False,
            gap_count=0,
            gap_widths=(),
            space_after=(),
            space_gap_threshold_px=int(max(1, min_space_gap_px)),
            cut_columns=(),
            unreliable_reason="empty_input",
        )

    binary_mask = _binarize_white_text_on_black(preprocessed_line)
    h, w = binary_mask.shape[:2]
    if h < 3 or w < 3:
        return VerticalSliceResult(
            preprocessed_line=preprocessed_line,
            binary_mask=binary_mask,
            slices=(),
            expected_char_count=0,
            confidence=0.0,
            reliable=False,
            gap_count=0,
            gap_widths=(),
            space_after=(),
            space_gap_threshold_px=int(max(1, min_space_gap_px)),
            cut_columns=(),
            unreliable_reason="too_small",
        )

    col_ink = (binary_mask > 0).sum(axis=0).astype(np.int32)
    active = col_ink > int(max(0, max_gap_ink_px))

    runs: list[tuple[int, int]] = []
    start: int | None = None
    for idx, on in enumerate(active.tolist()):
        if on and start is None:
            start = idx
        elif not on and start is not None:
            if idx - start >= int(min_slice_width_px):
                runs.append((start, idx))
            start = None
    if start is not None and w - start >= int(min_slice_width_px):
        runs.append((start, w))

    slices: list[CharSlice] = []
    for x1, x2 in runs:
        crop = binary_mask[:, x1:x2]
        if crop.size == 0:
            continue
        ys = np.flatnonzero(crop.any(axis=1))
        if ys.size == 0:
            continue
        local_ink_top = int(ys[0])
        local_ink_bottom = int(ys[-1]) + 1
        local_height = int(local_ink_bottom - local_ink_top)
        ink_pixels = int((crop > 0).sum())
        ink_density = float((crop > 0).mean())
        strong_columns = int(((crop > 0).sum(axis=0) >= int(max(1, strong_column_ink_px))).sum())
        if local_height < int(min_slice_height_px):
            continue
        if ink_pixels < int(min_ink_pixels_px):
            continue
        if ink_density < float(min_ink_ratio):
            continue
        if strong_columns < int(max(1, min_strong_columns_px)):
            continue
        slices.append(
            CharSlice(
                x=int(x1),
                y=0,
                width=max(1, int(x2 - x1)),
                height=int(h),
                ink_density=ink_density,
                local_ink_top=local_ink_top,
                local_ink_bottom=local_ink_bottom,
            )
        )

    slice_tuple = tuple(slices)
    if not slice_tuple:
        return VerticalSliceResult(
            preprocessed_line=preprocessed_line,
            binary_mask=binary_mask,
            slices=(),
            expected_char_count=0,
            confidence=0.0,
            reliable=False,
            gap_count=0,
            gap_widths=(),
            space_after=(),
            space_gap_threshold_px=int(max(1, min_space_gap_px)),
            cut_columns=(),
            unreliable_reason="no_ink_runs",
        )

    unreliable_reason = _coarse_blob_reason(slice_tuple, line_width=w, line_height=h)
    reliable = not bool(unreliable_reason)
    expected_char_count = len(slice_tuple) if reliable else 0

    gap_widths = tuple(
        max(0, slice_tuple[idx].x - (slice_tuple[idx - 1].x + slice_tuple[idx - 1].width))
        for idx in range(1, len(slice_tuple))
    )
    gap_count = sum(1 for gap in gap_widths if gap > 0)
    space_gap_threshold_px = _space_threshold_px(
        slice_tuple,
        gap_widths,
        min_space_gap_px=int(min_space_gap_px),
        space_gap_ratio=float(space_gap_ratio),
    )
    space_after = tuple(gap >= space_gap_threshold_px for gap in gap_widths)

    widths = np.asarray([s.width for s in slice_tuple], dtype=np.float32)
    mean_density = float(np.mean([s.ink_density for s in slice_tuple]))
    width_var = float(np.std(widths) / max(1.0, float(np.mean(widths)))) if widths.size > 1 else 0.0
    confidence = 0.0
    if reliable:
        confidence += 0.5 if len(slice_tuple) >= 2 else 0.2
        confidence += max(0.0, min(mean_density / 0.25, 1.0)) * 0.3
        confidence += max(0.0, 1.0 - min(width_var, 1.0)) * 0.2
    confidence = max(0.0, min(confidence, 1.0))

    cut_columns = tuple(int(sl.x + sl.width) for sl in slice_tuple[:-1])
    return VerticalSliceResult(
        preprocessed_line=preprocessed_line,
        binary_mask=binary_mask,
        slices=slice_tuple,
        expected_char_count=expected_char_count,
        confidence=confidence,
        reliable=reliable,
        gap_count=gap_count,
        gap_widths=gap_widths,
        space_after=space_after,
        space_gap_threshold_px=space_gap_threshold_px,
        cut_columns=cut_columns,
        unreliable_reason=unreliable_reason,
    )


def reconstruct_slice_text(result: VerticalSliceResult, chars: tuple[str, ...]) -> str:
    if not chars:
        return ""

    pieces: list[str] = []
    for idx, raw_char in enumerate(chars):
        char = str(raw_char or "").replace("\n", " ").strip()
        if char:
            pieces.append(char[0])
        should_insert_space = idx < len(result.space_after) and bool(result.space_after[idx])
        if should_insert_space and pieces and pieces[-1] != " ":
            if any(str(item or "").strip() for item in chars[idx + 1 :]):
                pieces.append(" ")
    return "".join(pieces).strip()
