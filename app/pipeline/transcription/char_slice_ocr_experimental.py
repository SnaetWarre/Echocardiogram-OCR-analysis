"""
Notebook / evaluation utilities: run the primary (and optional fallback) OCR engine on each
vertical ``CharSlice`` of a preprocessed line image and join results into a single string.

Used by ``LineTranscriber`` for a vertical per-slice OCR retry, and by notebooks and sweeps
for evaluation.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from app.pipeline.ocr.ocr_engines import OcrEngine
from app.pipeline.transcription.dead_space_char_splitter import CharSlice


def _one_visible_char(ocr_text: str) -> str:
    t = (ocr_text or "").replace("\n", " ").strip()
    if not t:
        return ""
    return t[0]


def per_char_slice_ocr_line(
    line_image: np.ndarray,
    slices: tuple[CharSlice, ...],
    *,
    primary_engine: OcrEngine,
    fallback_engine: OcrEngine | None = None,
    preprocessor: Callable[[np.ndarray], np.ndarray] | None = None,
    fallback_min_primary_conf: float = 0.45,
) -> tuple[str, float, float, tuple[float, ...]]:
    """
    Crop each ``CharSlice`` from ``line_image``, optionally preprocess, run ``extract``,
    and concatenate one character per slice (first character of OCR text).

    Returns ``(line_text, mean_confidence, min_confidence, per_slice_confidences)``.
    """
    if not slices or line_image.size == 0:
        return "", 0.0, 0.0, ()

    pre = preprocessor or (lambda g: g)
    confs: list[float] = []
    parts: list[str] = []

    h = int(line_image.shape[0])
    w = int(line_image.shape[1])

    for sl in slices:
        x1 = max(0, int(sl.x))
        y1 = max(0, int(sl.y))
        x2 = min(w, x1 + int(sl.width))
        y2 = min(h, y1 + int(sl.height))
        if y2 <= y1 or x2 <= x1:
            parts.append("")
            confs.append(0.0)
            continue

        crop = line_image[y1:y2, x1:x2]
        try:
            processed = pre(crop)
        except Exception:
            parts.append("")
            confs.append(0.0)
            continue
        if processed is None or (hasattr(processed, "size") and processed.size == 0):
            parts.append("")
            confs.append(0.0)
            continue

        res = primary_engine.extract(processed)
        conf = float(res.confidence)
        text = (res.text or "")

        if (
            fallback_engine is not None
            and conf < float(fallback_min_primary_conf)
        ):
            try:
                alt = fallback_engine.extract(processed)
                if float(alt.confidence) > conf:
                    res = alt
                    conf = float(alt.confidence)
                    text = (res.text or "")
            except Exception:
                pass

        parts.append(_one_visible_char(text))
        confs.append(conf)

    line_text = "".join(parts)
    if not confs:
        return line_text, 0.0, 0.0, ()
    mean_c = float(sum(confs) / len(confs))
    min_c = float(min(confs))
    return line_text, mean_c, min_c, tuple(confs)
