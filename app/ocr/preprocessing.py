from __future__ import annotations

import importlib
import os
from typing import Any

import numpy as np


DEFAULT_SCALE_FACTOR = 3
DEFAULT_SCALE_ALGO = "lanczos"
DEFAULT_CONTRAST_MODE = "none"


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        rgb = image[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {image.shape}")


def preprocess_roi(
    roi: np.ndarray,
    scale_factor: int | None = DEFAULT_SCALE_FACTOR,
    scale_algo: str | None = DEFAULT_SCALE_ALGO,
    contrast_mode: str | None = DEFAULT_CONTRAST_MODE,
    smooth: bool = False,
) -> np.ndarray:
    if scale_factor is None:
        try:
            scale_factor = int(os.getenv("ECHO_OCR_UPSCALE_FACTOR", str(DEFAULT_SCALE_FACTOR)))
        except (TypeError, ValueError):
            scale_factor = DEFAULT_SCALE_FACTOR
    if scale_algo is None:
        scale_algo = os.getenv("ECHO_OCR_UPSCALE_INTERPOLATION", DEFAULT_SCALE_ALGO).lower()
    if contrast_mode is None:
        contrast_mode = os.getenv("ECHO_OCR_CONTRAST_MODE", DEFAULT_CONTRAST_MODE).lower()

    gray = _to_gray(roi)
    if gray.size == 0:
        return gray

    try:
        cv2: Any = importlib.import_module("cv2")

        if contrast_mode == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        elif contrast_mode == "adaptive_threshold":
            enhanced = cv2.equalizeHist(gray)
        else:
            enhanced = gray

        gaussian = cv2.GaussianBlur(enhanced, (5, 5), 1.0)
        unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

        scale = max(1, min(scale_factor, 6))
        if scale > 1:
            interpolation_map = {
                "linear": cv2.INTER_LINEAR,
                "cubic": cv2.INTER_CUBIC,
                "lanczos": cv2.INTER_LANCZOS4,
            }
            inter_flag = interpolation_map.get(scale_algo, cv2.INTER_CUBIC)
            width = int(unsharp.shape[1] * scale)
            height = int(unsharp.shape[0] * scale)
            unsharp = cv2.resize(unsharp, (width, height), interpolation=inter_flag)

        if contrast_mode == "adaptive_threshold":
            thresh = cv2.adaptiveThreshold(
                unsharp,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2,
            )
        else:
            _, thresh = cv2.threshold(unsharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        clean = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        if smooth:
            blurred = cv2.GaussianBlur(clean, (3, 3), 0.6)
            _, clean = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

        return clean

    except ImportError:
        p5 = np.percentile(gray, 5)
        p95 = np.percentile(gray, 95)
        if p95 <= p5:
            stretched = gray
        else:
            stretched = (
                ((gray.astype(np.float32) - p5) * (255.0 / (p95 - p5)))
                .clip(0, 255)
                .astype(np.uint8)
            )

        scale = max(1, min(scale_factor, 6))
        if scale <= 1:
            return stretched
        return np.repeat(np.repeat(stretched, scale, axis=0), scale, axis=1)
