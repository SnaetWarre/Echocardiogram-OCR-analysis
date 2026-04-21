from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CharSlice:
    x: int
    y: int
    width: int
    height: int
    ink_density: float


@dataclass(frozen=True)
class DeadSpaceSplitResult:
    slices: tuple[CharSlice, ...]
    expected_char_count: int
    confidence: float
    gap_count: int


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        return cv2.cvtColor(image[..., :3].astype(np.uint8, copy=False), cv2.COLOR_BGR2GRAY)
    raise ValueError(f"Unsupported line image shape: {image.shape}")


def split_dead_space_char_slices(
    line_image: np.ndarray,
    *,
    min_ink_ratio: float = 0.03,
    min_column_ratio: float = 0.02,
    min_slice_width_px: int = 2,
    min_gap_width_px: int = 1,
) -> DeadSpaceSplitResult:
    gray = _to_gray(line_image)
    if gray.size == 0:
        return DeadSpaceSplitResult(slices=(), expected_char_count=0, confidence=0.0, gap_count=0)

    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return DeadSpaceSplitResult(slices=(), expected_char_count=0, confidence=0.0, gap_count=0)

    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2.0,
    )
    h, w = binary.shape
    col_ink = (binary > 0).sum(axis=0).astype(np.float32)
    min_col_ink = max(1.0, float(h) * float(min_column_ratio))
    active = col_ink >= min_col_ink

    runs: list[tuple[int, int]] = []
    start = None
    for idx, on in enumerate(active.tolist()):
        if on and start is None:
            start = idx
        elif not on and start is not None:
            if idx - start >= int(min_slice_width_px):
                runs.append((start, idx))
            start = None
    if start is not None and w - start >= int(min_slice_width_px):
        runs.append((start, w))

    if not runs:
        return DeadSpaceSplitResult(slices=(), expected_char_count=0, confidence=0.0, gap_count=0)

    slices: list[CharSlice] = []
    for x1, x2 in runs:
        crop = binary[:, x1:x2]
        ys, xs = np.where(crop > 0)
        if ys.size == 0:
            continue
        y1 = int(ys.min())
        y2 = int(ys.max()) + 1
        ink_density = float((crop > 0).mean())
        if ink_density < float(min_ink_ratio):
            continue
        slices.append(
            CharSlice(
                x=int(x1),
                y=int(y1),
                width=max(1, int(x2 - x1)),
                height=max(1, int(y2 - y1)),
                ink_density=ink_density,
            )
        )

    if not slices:
        return DeadSpaceSplitResult(slices=(), expected_char_count=0, confidence=0.0, gap_count=0)

    widths = np.asarray([s.width for s in slices], dtype=np.float32)
    width_var = float(np.std(widths) / max(1.0, float(np.mean(widths)))) if widths.size > 1 else 0.0
    mean_density = float(np.mean([s.ink_density for s in slices]))
    gap_count = 0
    for idx in range(1, len(slices)):
        prev = slices[idx - 1]
        curr = slices[idx]
        if curr.x - (prev.x + prev.width) >= int(min_gap_width_px):
            gap_count += 1

    confidence = 0.0
    confidence += 0.5 if len(slices) >= 2 else 0.2
    confidence += max(0.0, min(mean_density / 0.25, 1.0)) * 0.3
    confidence += max(0.0, 1.0 - min(width_var, 1.0)) * 0.2
    confidence = max(0.0, min(confidence, 1.0))

    return DeadSpaceSplitResult(
        slices=tuple(slices),
        expected_char_count=len(slices),
        confidence=confidence,
        gap_count=gap_count,
    )
