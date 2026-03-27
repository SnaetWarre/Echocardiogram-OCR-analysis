from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RoiDetection:
    present: bool
    bbox: tuple[int, int, int, int] | None
    confidence: float


# Measurement overlay box color (hex #1A2129) - dark blue-gray
_MEASUREMENT_BOX_RGB = (0x1A, 0x21, 0x29)
_MEASUREMENT_BOX_TOLERANCE = 5  # max absolute difference per channel (same order as frame[..., :3])


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame.astype(np.uint8, copy=False)
    if frame.ndim == 3 and frame.shape[-1] >= 3:
        rgb = frame[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {frame.shape}")


def _color_match_mask(pixels: np.ndarray, target: tuple[int, ...], tolerance: float) -> np.ndarray:
    """True where every channel is within ``tolerance`` of ``target`` (per channel, not Euclidean)."""
    tol = float(tolerance)
    if len(target) < 3:
        raise ValueError("target must have at least three channel values")
    tr, tg, tb = float(target[0]), float(target[1]), float(target[2])
    p = pixels[..., :3].astype(np.float32, copy=False)
    return (np.abs(p[..., 0] - tr) <= tol) & (np.abs(p[..., 1] - tg) <= tol) & (np.abs(p[..., 2] - tb) <= tol)


def _color_max_channel_abs_diff(pixels: np.ndarray, target: tuple[int, ...]) -> np.ndarray:
    """Maximum over channels of |pixel[c] - target[c]| (for debug heatmaps)."""
    if len(target) < 3:
        raise ValueError("target must have at least three channel values")
    tr, tg, tb = float(target[0]), float(target[1]), float(target[2])
    p = pixels[..., :3].astype(np.float32, copy=False)
    return np.maximum(np.maximum(np.abs(p[..., 0] - tr), np.abs(p[..., 1] - tg)), np.abs(p[..., 2] - tb))


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

    def detect(self, frame: np.ndarray) -> RoiDetection:
        search = frame

        if search.ndim != 3 or search.shape[-1] < 3:
            return RoiDetection(present=False, bbox=None, confidence=0.0)
        else:
            rgb = search[..., :3]
            mask = _color_match_mask(rgb, self.box_color, self.color_tolerance)

            if np.sum(mask) >= self.min_pixels:
                component_mask = _fill_mask_holes(mask)
                mask = _select_measurement_component(component_mask)
            else:
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
