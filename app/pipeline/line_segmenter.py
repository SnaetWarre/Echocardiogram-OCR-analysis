from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence, cast

import numpy as np

from app.pipeline.ocr_engines import OcrToken


DEFAULT_HEADER_TRIM_PX = 14


def _empty_metadata() -> dict[str, Any]:
    return {}


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        rgb = image[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported ROI shape: {image.shape}")


@dataclass(frozen=True)
class SegmentedLine:
    order: int
    bbox: tuple[int, int, int, int]
    component_boxes: tuple[tuple[int, int, int, int], ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True)
class SegmentationResult:
    header_trim_px: int
    content_bbox: tuple[int, int, int, int] | None
    lines: tuple[SegmentedLine, ...] = field(default_factory=tuple)
    used_token_boxes: bool = False
    used_projection_fallback: bool = False
    debug: dict[str, Any] = field(default_factory=_empty_metadata)


class LineSegmenter:
    def __init__(
        self,
        *,
        default_header_trim_px: int = DEFAULT_HEADER_TRIM_PX,
        projection_threshold_ratio: float = 0.012,
        min_line_height_px: int = 4,
        line_padding_px: int = 2,
        merge_gap_px: int = 3,
        max_header_fraction: float = 0.45,
    ) -> None:
        self.default_header_trim_px = max(0, int(default_header_trim_px))
        self.projection_threshold_ratio = max(0.001, float(projection_threshold_ratio))
        self.min_line_height_px = max(1, int(min_line_height_px))
        self.line_padding_px = max(0, int(line_padding_px))
        self.merge_gap_px = max(0, int(merge_gap_px))
        self.max_header_fraction = min(max(float(max_header_fraction), 0.0), 1.0)

    def segment(
        self,
        roi: np.ndarray,
        *,
        tokens: Sequence[OcrToken] | None = None,
    ) -> SegmentationResult:
        gray = _to_gray(roi)
        if gray.size == 0:
            return SegmentationResult(header_trim_px=0, content_bbox=None, lines=())

        header_trim_px = self.detect_header_trim(gray)
        content = gray[header_trim_px:, :]
        content_bbox = None
        if content.size > 0:
            content_bbox = (0, header_trim_px, int(content.shape[1]), int(content.shape[0]))

        lines: list[SegmentedLine] = []
        used_token_boxes = False
        if tokens:
            lines = self._segment_from_tokens(
                tokens,
                content_shape=(int(content.shape[0]), int(content.shape[1])) if content.ndim == 2 else (0, 0),
                header_trim_px=header_trim_px,
            )
            used_token_boxes = bool(lines)

        used_projection_fallback = False
        if not lines:
            lines = self._segment_from_projection(content, header_trim_px=header_trim_px)
            used_projection_fallback = True

        if not lines and content.size > 0:
            lines = [
                SegmentedLine(
                    order=0,
                    bbox=(0, header_trim_px, int(content.shape[1]), int(content.shape[0])),
                    component_boxes=((0, header_trim_px, int(content.shape[1]), int(content.shape[0])),),
                    metadata={"recovered": True, "reason": "empty_segmentation"},
                )
            ]

        return SegmentationResult(
            header_trim_px=header_trim_px,
            content_bbox=content_bbox,
            lines=tuple(lines),
            used_token_boxes=used_token_boxes,
            used_projection_fallback=used_projection_fallback,
            debug={"line_count": len(lines), "header_trim_px": header_trim_px},
        )

    def detect_header_trim(self, roi: np.ndarray) -> int:
        gray = _to_gray(roi)
        if gray.size == 0:
            return 0

        mask = self._text_mask(gray)
        row_density = mask.mean(axis=1) if mask.size else np.zeros(gray.shape[0], dtype=np.float32)
        width = max(1, int(gray.shape[1]))
        row_threshold = max(self.projection_threshold_ratio, 1.0 / width)
        runs = self._contiguous_runs(row_density >= row_threshold)
        if not runs:
            return min(self.default_header_trim_px, max(0, int(gray.shape[0]) - 1))

        max_header_start = max(0, int(gray.shape[0] * self.max_header_fraction))
        first_start, first_end = runs[0]

        if len(runs) >= 2 and first_start <= self.default_header_trim_px:
            second_start, _second_end = runs[1]
            gap = second_start - first_end - 1
            first_height = first_end - first_start + 1
            if gap >= max(2, min(6, first_height)):
                return min(second_start, max_header_start)

        if first_start > 0:
            return min(first_start, max_header_start)

        if len(runs) >= 2:
            second_start, _second_end = runs[1]
            gap = second_start - first_end - 1
            first_height = first_end - first_start + 1
            if gap >= max(2, min(6, first_height)):
                return min(second_start, max_header_start)

        return min(self.default_header_trim_px, max_header_start)

    def save_debug_image(self, roi: np.ndarray, result: SegmentationResult, output_path: Path) -> Path:
        try:
            cv2: Any = importlib.import_module("cv2")
        except ImportError as exc:  # pragma: no cover - debug helper only
            raise RuntimeError("OpenCV is required to save segmentation debug images.") from exc

        if roi.ndim == 2:
            canvas = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        else:
            canvas = roi.copy()

        height = int(canvas.shape[0])
        width = int(canvas.shape[1])

        if result.header_trim_px > 0:
            header_y = min(result.header_trim_px, max(0, height - 1))
            cv2.line(canvas, (0, header_y), (max(0, width - 1), header_y), (0, 255, 255), 1)

        for line in result.lines:
            x, y, w, h = line.bbox
            cv2.rectangle(canvas, (x, y), (x + w - 1, y + h - 1), (0, 255, 0), 1)
            cv2.putText(
                canvas,
                str(line.order + 1),
                (x, max(10, y + 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas)
        return output_path

    def _segment_from_tokens(
        self,
        tokens: Sequence[OcrToken],
        *,
        content_shape: tuple[int, int],
        header_trim_px: int,
    ) -> list[SegmentedLine]:
        height, width = content_shape
        if height <= 0 or width <= 0:
            return []

        valid_boxes: list[tuple[int, int, int, int]] = []
        for token in tokens:
            if token.bbox is None:
                continue
            x, y, w, h = token.bbox
            valid_boxes.append(
                (
                    max(0, int(round(x))),
                    max(0, int(round(y))),
                    max(1, int(round(w))),
                    max(1, int(round(h))),
                )
            )

        if not valid_boxes:
            return []

        rows: list[list[tuple[int, int, int, int]]] = []
        for box in sorted(valid_boxes, key=lambda item: (item[1], item[0])):
            center_y = box[1] + box[3] / 2.0
            attached = False
            for row in rows:
                row_top = min(item[1] for item in row)
                row_bottom = max(item[1] + item[3] for item in row)
                if row_top - self.merge_gap_px <= center_y <= row_bottom + self.merge_gap_px:
                    row.append(box)
                    attached = True
                    break
            if not attached:
                rows.append([box])

        lines: list[SegmentedLine] = []
        for order, row in enumerate(rows):
            x1 = max(0, min(item[0] for item in row) - self.line_padding_px)
            y1 = max(0, min(item[1] for item in row) - self.line_padding_px)
            x2 = min(width, max(item[0] + item[2] for item in row) + self.line_padding_px)
            y2 = min(height, max(item[1] + item[3] for item in row) + self.line_padding_px)
            lines.append(
                SegmentedLine(
                    order=order,
                    bbox=(x1, y1 + header_trim_px, max(1, x2 - x1), max(1, y2 - y1)),
                    component_boxes=tuple((x, y + header_trim_px, w, h) for x, y, w, h in row),
                    metadata={"source": "token_boxes", "token_count": len(row)},
                )
            )
        return lines

    def _segment_from_projection(self, content: np.ndarray, *, header_trim_px: int) -> list[SegmentedLine]:
        if content.size == 0:
            return []

        mask = self._text_mask(content)
        row_density = mask.mean(axis=1) if mask.size else np.zeros(content.shape[0], dtype=np.float32)
        width = max(1, int(content.shape[1]))
        density_peak = float(row_density.max()) if row_density.size else 0.0
        row_threshold = max(
            self.projection_threshold_ratio,
            min(0.18, density_peak * 0.35),
            1.0 / width,
        )
        active = row_density >= row_threshold
        active = self._fill_short_row_gaps(active)
        runs = self._merge_runs(self._contiguous_runs(active))
        if not runs:
            return []

        lines: list[SegmentedLine] = []
        for start, end in runs:
            if end - start + 1 < self.min_line_height_px:
                continue
            band = mask[start : end + 1, :]
            _ys, xs = np.where(band)
            if xs.size == 0:
                x1, x2 = 0, int(content.shape[1])
            else:
                x1 = max(0, int(xs.min()) - self.line_padding_px)
                x2 = min(int(content.shape[1]), int(xs.max()) + self.line_padding_px + 1)
            y1 = max(0, start - self.line_padding_px)
            y2 = min(int(content.shape[0]), end + self.line_padding_px + 1)
            lines.append(
                SegmentedLine(
                    order=len(lines),
                    bbox=(x1, y1 + header_trim_px, max(1, x2 - x1), max(1, y2 - y1)),
                    component_boxes=((x1, y1 + header_trim_px, max(1, x2 - x1), max(1, y2 - y1)),),
                    metadata={"source": "projection"},
                )
            )

        return lines

    def _text_mask(self, image: np.ndarray) -> np.ndarray:
        gray = _to_gray(image)
        if gray.size == 0:
            return np.zeros_like(gray, dtype=bool)

        try:
            cv2: Any = importlib.import_module("cv2")
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            _threshold, binary = cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            mask = binary > 0
            if float(mask.mean()) > 0.55:
                mask = binary == 0
            kernel = np.ones((2, 2), dtype=np.uint8)
            mask_u8 = mask.astype(np.uint8) * 255
            mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)
            mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)
            return mask_u8 > 0
        except ImportError:
            high_threshold = max(float(np.percentile(gray, 82)), float(gray.mean() + gray.std() * 0.25))
            mask = gray >= high_threshold
            if float(mask.mean()) > 0.55:
                low_threshold = min(float(np.percentile(gray, 18)), float(gray.mean() - gray.std() * 0.25))
                mask = gray <= low_threshold
            return mask

    def _fill_short_row_gaps(self, active: np.ndarray) -> np.ndarray:
        if active.size == 0:
            return active
        filled = active.copy()
        gap_start: int | None = None
        for idx, flag in enumerate(cast(list[bool], filled.tolist())):
            if flag:
                gap_start = None
                continue
            if gap_start is None:
                gap_start = idx
            next_is_inactive = idx + 1 < filled.size and not bool(filled[idx + 1])
            if next_is_inactive:
                continue
            gap_end = idx
            gap_before = gap_start > 0 and bool(filled[gap_start - 1])
            gap_after = idx + 1 < filled.size and bool(filled[idx + 1])
            gap_size = gap_end - gap_start + 1
            if gap_before and gap_after and gap_size <= self.merge_gap_px:
                filled[gap_start : gap_end + 1] = True
            gap_start = None
        return filled

    def _merge_runs(self, runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if not runs:
            return []
        merged: list[tuple[int, int]] = [runs[0]]
        for start, end in runs[1:]:
            prev_start, prev_end = merged[-1]
            prev_height = prev_end - prev_start + 1
            current_height = end - start + 1
            gap = start - prev_end - 1
            if gap <= self.merge_gap_px or min(prev_height, current_height) < self.min_line_height_px:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))
        return merged

    @staticmethod
    def _contiguous_runs(active: np.ndarray) -> list[tuple[int, int]]:
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for idx, flag in enumerate(cast(list[bool], active.tolist())):
            if flag and start is None:
                start = idx
            elif not flag and start is not None:
                runs.append((start, idx - 1))
                start = None
        if start is not None:
            runs.append((start, int(active.size) - 1))
        return runs
