from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RoiDetection:
    present: bool
    bbox: tuple[int, int, int, int] | None
    confidence: float


# Measurement overlay box color (hex #1A2129, rgb 26, 33, 41) 
_MEASUREMENT_BOX_RGB = (0x1A, 0x21, 0x29)
_MEASUREMENT_BOX_TOLERANCE = 6


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame.astype(np.uint8, copy=False)
    if frame.ndim == 3 and frame.shape[-1] >= 3:
        rgb = frame[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {frame.shape}")


def _color_match_mask(rgb: np.ndarray, target: tuple[int, int, int], tolerance: float) -> np.ndarray:
    """Pixels where each RGB channel is within ``tolerance`` of ``target`` (absolute difference)."""
    # Convert to signed ints so channel subtraction is safe for uint8 inputs.
    rgb_int = rgb[..., :3].astype(np.int16, copy=False)

    target_r, target_g, target_b = (int(channel) for channel in target)
    max_channel_delta = float(tolerance)

    red_delta = np.abs(rgb_int[..., 0] - target_r)
    green_delta = np.abs(rgb_int[..., 1] - target_g)
    blue_delta = np.abs(rgb_int[..., 2] - target_b)

    red_matches = red_delta <= max_channel_delta
    green_matches = green_delta <= max_channel_delta
    blue_matches = blue_delta <= max_channel_delta

    return red_matches & green_matches & blue_matches


def _select_measurement_component(mask: np.ndarray) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return mask

    mask_u8 = mask.astype(np.uint8, copy=False)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if num_labels <= 1:
        return mask

    best_label = 0
    best_score = float("-inf")
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area <= 0:
            continue

        left = float(stats[label, cv2.CC_STAT_LEFT])
        top = float(stats[label, cv2.CC_STAT_TOP])
        width = float(stats[label, cv2.CC_STAT_WIDTH])
        height = float(stats[label, cv2.CC_STAT_HEIGHT])
        centroid_x = float(centroids[label][0])
        centroid_y = float(centroids[label][1])

        if left > 220 or top > 120:
            continue
        if width < 40 or height < 12:
            continue

        score = (
            4.0 * area
            - 120.0 * left
            - 160.0 * top
            - 40.0 * centroid_x
            - 60.0 * centroid_y
        )
        if score > best_score:
            best_score = score
            best_label = label

    if best_label == 0:
        return np.zeros_like(mask, dtype=bool)
    return labels == best_label


def _fill_mask_holes(mask: np.ndarray) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return mask

    mask_u8 = mask.astype(np.uint8, copy=False) * 255
    h, w = mask_u8.shape
    flood = mask_u8.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    filled = cv2.bitwise_or(mask_u8, holes)
    return filled > 0


class TopLeftBlueGrayBoxDetector:
    def __init__(
        self,
        *,
        min_pixels: int = 240,
        min_presence_confidence: float = 0.04,
        box_color: tuple = _MEASUREMENT_BOX_RGB,
        color_tolerance: float = _MEASUREMENT_BOX_TOLERANCE,
    ) -> None:
        self.min_pixels = min_pixels
        self.min_presence_confidence = min_presence_confidence
        self.box_color = box_color
        self.color_tolerance = color_tolerance

    def _foreground_mask(self, frame: np.ndarray) -> np.ndarray | None:
        if frame.ndim != 3 or frame.shape[-1] < 3:
            return None
        rgb = frame[..., :3].astype(np.int16)
        mask = _color_match_mask(rgb, self.box_color, self.color_tolerance)
        if int(np.sum(mask)) < self.min_pixels:
            return None
        filled = _fill_mask_holes(mask)
        return _select_measurement_component(filled)

    def detect(self, frame: np.ndarray) -> RoiDetection:
        mask = self._foreground_mask(frame)
        if mask is None:
            return RoiDetection(present=False, bbox=None, confidence=0.0)

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
