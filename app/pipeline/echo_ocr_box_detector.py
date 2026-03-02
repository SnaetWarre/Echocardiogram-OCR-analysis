from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class RoiDetection:
    present: bool
    bbox: Optional[Tuple[int, int, int, int]]
    confidence: float


# Measurement overlay box color (hex #1A2129) - dark blue-gray
_MEASUREMENT_BOX_RGB = (0x1A, 0x21, 0x29)
_MEASUREMENT_BOX_TOLERANCE = 55  # max Euclidean distance in RGB to match


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame.astype(np.uint8, copy=False)
    if frame.ndim == 3 and frame.shape[-1] >= 3:
        rgb = frame[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {frame.shape}")


def _color_distance(rgb: np.ndarray, target: tuple) -> np.ndarray:
    """Euclidean distance in RGB space from target."""
    rgb_f = rgb[..., :3].astype(np.float32, copy=False)
    tr, tg, tb = map(float, target)
    dr = rgb_f[..., 0] - tr
    dg = rgb_f[..., 1] - tg
    db = rgb_f[..., 2] - tb
    return np.sqrt(np.maximum(dr * dr + dg * dg + db * db, 0.0))


class TopLeftBlueGrayBoxDetector:
    def __init__(
        self,
        *,
        top_left_height_ratio: float = 0.45,
        top_left_width_ratio: float = 0.55,
        min_pixels: int = 240,
        min_presence_confidence: float = 0.04,
        box_color: tuple = _MEASUREMENT_BOX_RGB,
        color_tolerance: float = _MEASUREMENT_BOX_TOLERANCE,
    ) -> None:
        self.top_left_height_ratio = top_left_height_ratio
        self.top_left_width_ratio = top_left_width_ratio
        self.min_pixels = min_pixels
        self.min_presence_confidence = min_presence_confidence
        self.box_color = box_color
        self.color_tolerance = color_tolerance

    def detect(self, frame: np.ndarray) -> RoiDetection:
        h, w = frame.shape[:2]
        roi_h = max(8, int(h * self.top_left_height_ratio))
        roi_w = max(8, int(w * self.top_left_width_ratio))
        search = frame[:roi_h, :roi_w]

        if search.ndim != 3 or search.shape[-1] < 3:
            gray = _to_gray(search)
            mask = gray > 180
        else:
            rgb = search[..., :3].astype(np.int16)
            # Primary: match #1A2129 (measurement overlay box)
            dist = _color_distance(rgb, self.box_color)
            mask = dist <= self.color_tolerance
            # Fallback: original blue-gray heuristic for variants
            if np.sum(mask) < self.min_pixels:
                r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
                mask = (b > 70) & (g > 65) & (r > 45) & (b >= r) & (np.abs(g - b) < 70)

        ys, xs = np.where(mask)
        if xs.size < self.min_pixels:
            return RoiDetection(present=False, bbox=None, confidence=0.0)

        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        width = max(x2 - x1 + 1, 1)
        height = max(y2 - y1 + 1, 1)
        area = width * height
        if area <= 0:
            return RoiDetection(present=False, bbox=None, confidence=0.0)
        fill_ratio = float(xs.size / area)
        confidence = float(min(1.0, fill_ratio))
        if confidence < self.min_presence_confidence:
            return RoiDetection(present=False, bbox=None, confidence=confidence)
        return RoiDetection(present=True, bbox=(x1, y1, width, height), confidence=confidence)
