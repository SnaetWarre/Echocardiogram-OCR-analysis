from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence, cast

import numpy as np

from app.pipeline.ocr_engines import OcrToken


DEFAULT_HEADER_TRIM_PX = 12
# Upper bound on header trim so the first measurement line keeps its ascenders;
# detection can otherwise jump to ~45% of ROI height or the second text run (often ~24px).
DEFAULT_MAX_HEADER_TRIM_PX = 18


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
    """Split a measurement-panel ROI into horizontal text lines.

    *Default (`row_projection`)*: B&W text mask, horizontal ink projection, gap rows, line
    bands split at **gap midpoints** (``_segment_from_projection``), then optional local
    refinement for merged tall crops.

    *Adaptive* (any other mode, e.g. ``adaptive``): OCR token row clustering first, then
    projection if needed, then refinement.

    *Horizontal* extent per line: tight bbox from mask / components plus `line_padding_px`
    (default 2). Use `extra_left_pad_px` to widen leftward for faint leading glyphs.

    `target_line_height_px` is kept for pipeline / UI config compatibility (hint in ``debug``);
    row geometry is driven by the projection, not by a fixed stripe height.
    """

    def __init__(
        self,
        *,
        segmentation_mode: str = "row_projection",
        target_line_height_px: float = 20.0,
        default_header_trim_px: int = DEFAULT_HEADER_TRIM_PX,
        max_header_trim_px: int | None = DEFAULT_MAX_HEADER_TRIM_PX,
        projection_threshold_ratio: float = 0.012,
        min_line_height_px: int = 4,
        line_padding_px: int = 2,
        merge_gap_px: int = 3,
        max_header_fraction: float = 0.45,
        refine_split_min_height_px: int = 10,
        extra_left_pad_px: int = 0,
    ) -> None:
        mode = str(segmentation_mode).strip().lower() or "row_projection"
        if mode == "fixed_pitch":
            mode = "row_projection"
        self.segmentation_mode = mode
        self.target_line_height_px = max(1.0, float(target_line_height_px))
        self.default_header_trim_px = max(0, int(default_header_trim_px))
        self.max_header_trim_px = (
            None if max_header_trim_px is None else max(0, int(max_header_trim_px))
        )
        self.projection_threshold_ratio = max(0.001, float(projection_threshold_ratio))
        self.min_line_height_px = max(1, int(min_line_height_px))
        self.line_padding_px = max(0, int(line_padding_px))
        # Pixels subtracted from x1 (expand crop left) after mask/tight bbox; helps faint leading text.
        self.extra_left_pad_px = max(0, int(extra_left_pad_px))
        self.merge_gap_px = max(0, int(merge_gap_px))
        self.max_header_fraction = min(max(float(max_header_fraction), 0.0), 1.0)
        self.refine_split_min_height_px = max(self.min_line_height_px * 2, int(refine_split_min_height_px))

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

        if self.segmentation_mode == "row_projection":
            lines = self._segment_from_projection(content, header_trim_px=header_trim_px)
            if not lines and content.size > 0:
                lines = [
                    SegmentedLine(
                        order=0,
                        bbox=(0, header_trim_px, int(content.shape[1]), int(content.shape[0])),
                        component_boxes=((0, header_trim_px, int(content.shape[1]), int(content.shape[0])),),
                        metadata={
                            "recovered": True,
                            "reason": "empty_row_projection",
                            "source": "row_projection",
                        },
                    )
                ]
            initial_line_count = len(lines)
            lines = self._refine_segmented_lines(gray, lines)
            return SegmentationResult(
                header_trim_px=header_trim_px,
                content_bbox=content_bbox,
                lines=tuple(lines),
                used_token_boxes=False,
                used_projection_fallback=False,
                debug={
                    "line_count": len(lines),
                    "header_trim_px": header_trim_px,
                    "refined_line_splits": max(0, len(lines) - initial_line_count),
                    "segmentation_mode": self.segmentation_mode,
                    "target_line_height_px": self.target_line_height_px,
                },
            )

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

        initial_line_count = len(lines)
        lines = self._refine_segmented_lines(gray, lines)

        return SegmentationResult(
            header_trim_px=header_trim_px,
            content_bbox=content_bbox,
            lines=tuple(lines),
            used_token_boxes=used_token_boxes,
            used_projection_fallback=used_projection_fallback,
            debug={
                "line_count": len(lines),
                "header_trim_px": header_trim_px,
                "refined_line_splits": max(0, len(lines) - initial_line_count),
                "segmentation_mode": self.segmentation_mode,
                "target_line_height_px": self.target_line_height_px,
            },
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
        if self.max_header_trim_px is not None:
            max_header_start = min(max_header_start, self.max_header_trim_px)
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

    def debug_row_projection_scan(
        self,
        roi: np.ndarray,
        *,
        header_trim_px: int,
    ) -> dict[str, Any]:
        """Diagnostics aligned with `row_projection` / `_projection_runs_from_mask` (for notebooks)."""
        if roi.size == 0:
            return {
                "mask_u8": np.zeros((0, 0), dtype=np.uint8),
                "row_ink": np.zeros((0,), dtype=np.float32),
                "tau": 0.0,
                "gap_mid_y_content": [],
                "content_shape": (0, 0),
            }
        content = roi[header_trim_px:]
        mask = self._text_mask(content)
        if mask.size == 0:
            return {
                "mask_u8": np.zeros((0, 0), dtype=np.uint8),
                "row_ink": np.zeros((0,), dtype=np.float32),
                "tau": 0.0,
                "gap_mid_y_content": [],
                "content_shape": (0, 0),
            }
        h, w = int(mask.shape[0]), int(mask.shape[1])
        row_ink = mask.mean(axis=1).astype(np.float32)
        peak = float(row_ink.max()) if h else 0.0
        tau = max(
            float(self.projection_threshold_ratio),
            min(0.18, peak * 0.35),
            1.0 / max(1, w),
        )
        runs = self._projection_runs_from_mask(mask, row_density=row_ink)
        gap_mid_y: list[int] = []
        for i in range(len(runs) - 1):
            g0 = runs[i][1] + 1
            g1 = runs[i + 1][0] - 1
            if g1 >= g0:
                gap_mid_y.append((g0 + g1) // 2)
        return {
            "mask_u8": (mask.astype(np.uint8) * 255),
            "row_ink": row_ink,
            "tau": float(tau),
            "gap_mid_y_content": gap_mid_y,
            "content_shape": (h, w),
        }

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

        raw_boxes: list[tuple[float, float, float, float]] = []
        for token in tokens:
            if token.bbox is None:
                continue
            x, y, a, b = token.bbox
            raw_boxes.append((float(x), float(y), float(a), float(b)))

        roi_height = height + max(0, int(header_trim_px))
        bbox_format = self._infer_token_bbox_format(raw_boxes, roi_width=width, roi_height=roi_height)
        valid_boxes: list[tuple[int, int, int, int]] = []
        for raw_box in raw_boxes:
            x, y, w, h = self._normalize_token_bbox(raw_box, bbox_format=bbox_format)
            x1 = max(0, min(int(round(x)), width))
            x2 = max(x1, min(int(round(x + w)), width))
            full_y1 = int(round(y))
            full_y2 = int(round(y + h))
            y1 = max(0, min(full_y1 - header_trim_px, height))
            y2 = max(y1, min(full_y2 - header_trim_px, height))
            if x2 <= x1 or y2 <= y1:
                continue
            valid_boxes.append((x1, y1, x2 - x1, y2 - y1))

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
            x1 = max(0, min(item[0] for item in row) - self.line_padding_px - self.extra_left_pad_px)
            y1 = max(0, min(item[1] for item in row) - self.line_padding_px)
            x2 = min(width, max(item[0] + item[2] for item in row) + self.line_padding_px)
            y2 = min(height, max(item[1] + item[3] for item in row) + self.line_padding_px)
            lines.append(
                SegmentedLine(
                    order=order,
                    bbox=(x1, y1 + header_trim_px, max(1, x2 - x1), max(1, y2 - y1)),
                    component_boxes=tuple((x, y + header_trim_px, w, h) for x, y, w, h in row),
                    metadata={"source": "token_boxes", "token_count": len(row), "token_bbox_format": bbox_format},
                )
            )
        return lines

    @staticmethod
    def _normalize_token_bbox(
        raw_box: tuple[float, float, float, float],
        *,
        bbox_format: str,
    ) -> tuple[float, float, float, float]:
        x, y, third, fourth = raw_box
        if bbox_format == "xyxy":
            return x, y, max(1.0, third - x), max(1.0, fourth - y)
        return x, y, max(1.0, third), max(1.0, fourth)

    def _infer_token_bbox_format(
        self,
        raw_boxes: Sequence[tuple[float, float, float, float]],
        *,
        roi_width: int,
        roi_height: int,
    ) -> str:
        if not raw_boxes:
            return "xywh"
        xywh_score = self._token_bbox_score(raw_boxes, roi_width=roi_width, roi_height=roi_height, bbox_format="xywh")
        xyxy_score = self._token_bbox_score(raw_boxes, roi_width=roi_width, roi_height=roi_height, bbox_format="xyxy")
        return "xyxy" if xyxy_score + 1e-6 < xywh_score else "xywh"

    def _token_bbox_score(
        self,
        raw_boxes: Sequence[tuple[float, float, float, float]],
        *,
        roi_width: int,
        roi_height: int,
        bbox_format: str,
    ) -> float:
        score = 0.0
        for raw_box in raw_boxes:
            x, y, w, h = self._normalize_token_bbox(raw_box, bbox_format=bbox_format)
            if w <= 0 or h <= 0:
                score += 1_000_000.0
                continue
            overflow_x = max(0.0, (x + w) - float(roi_width))
            overflow_y = max(0.0, (y + h) - float(roi_height))
            underflow_x = max(0.0, -x)
            underflow_y = max(0.0, -y)
            score += overflow_x + overflow_y + underflow_x + underflow_y
            if w >= float(roi_width) * 0.98:
                score += 10.0
            if h >= float(roi_height) * 0.5:
                score += 5.0
        return score

    def _segment_from_projection(self, content: np.ndarray, *, header_trim_px: int) -> list[SegmentedLine]:
        if content.size == 0:
            return []

        mask = self._text_mask(content)
        row_density = mask.mean(axis=1).astype(np.float32) if mask.size else np.zeros(content.shape[0], dtype=np.float32)
        runs = self._projection_runs_from_mask(mask, row_density=row_density)
        if not runs:
            return []

        return self._build_lines_from_runs(
            mask,
            runs,
            header_trim_px=header_trim_px,
            metadata_factory=lambda _order, _run, line_count: {
                "source": "projection",
                "placement": "gap_midpoint",
                "line_count": line_count,
            },
        )

    def _refine_segmented_lines(self, gray: np.ndarray, lines: list[SegmentedLine]) -> list[SegmentedLine]:
        if not lines:
            return []

        original_count = len(lines)
        heights = [line.bbox[3] for line in lines if line.bbox[3] > 0]
        median_height = float(np.median(np.asarray(heights, dtype=np.float32))) if heights else 0.0
        split_height_threshold = max(float(self.refine_split_min_height_px), median_height * 1.45)
        refined: list[SegmentedLine] = []
        for line in lines:
            if float(line.bbox[3]) < split_height_threshold:
                refined.append(line)
                continue
            split_lines = self._split_line_from_local_projection(
                gray,
                line,
                reference_height_px=max(1.0, median_height),
            )
            refined.extend(split_lines)

        if not refined:
            refined = list(lines)

        return [
            SegmentedLine(
                order=order,
                bbox=line.bbox,
                component_boxes=line.component_boxes,
                metadata={
                    **line.metadata,
                    "refined_line_count": len(refined),
                    "original_line_count": original_count,
                },
            )
            for order, line in enumerate(refined)
        ]

    def _split_line_from_local_projection(
        self,
        gray: np.ndarray,
        line: SegmentedLine,
        *,
        reference_height_px: float,
    ) -> list[SegmentedLine]:
        x, y, width, height = line.bbox
        if width <= 0 or height < self.refine_split_min_height_px:
            return [line]

        y1 = max(0, y)
        y2 = min(int(gray.shape[0]), y + height)
        x1 = max(0, x)
        x2 = min(int(gray.shape[1]), x + width)
        if x1 >= x2 or y1 >= y2:
            return [line]

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            return [line]

        mask = self._text_mask(crop)
        row_density = mask.mean(axis=1) if mask.size else np.zeros(crop.shape[0], dtype=np.float32)
        density_peak = float(row_density.max()) if row_density.size else 0.0
        local_threshold = max(
            self.projection_threshold_ratio,
            min(0.22, density_peak * 0.45),
            1.0 / max(1, int(crop.shape[1])),
        )
        active = row_density >= local_threshold
        active = self._fill_short_row_gaps(active)
        runs = [
            (start, end)
            for start, end in self._contiguous_runs(active)
            if end - start + 1 >= self.min_line_height_px
        ]
        if len(runs) < 2:
            return [line]
        max_split_count = max(2, int(round(height / max(reference_height_px, 1.0))) + 1)
        if len(runs) > max_split_count:
            return [line]

        boundaries = self._line_boundaries_from_runs(runs, content_height=int(crop.shape[0]))
        local_components = self._extract_component_boxes(mask)

        split_lines: list[SegmentedLine] = []
        for split_index, ((start, end), (band_top, band_bottom)) in enumerate(zip(runs, boundaries, strict=False)):
            split_y1 = max(0, y1 + band_top)
            split_y2 = min(int(gray.shape[0]), y1 + band_bottom)
            local_component_boxes = self._component_boxes_for_vertical_span(local_components, start, end + 1)
            component_boxes = tuple(
                (cx + x1, cy + y1, cw, ch) for cx, cy, cw, ch in local_component_boxes
            )
            split_x1, split_x2 = self._x_bounds_for_span(
                mask,
                span_top=band_top,
                span_bottom=band_bottom,
                content_width=int(gray.shape[1]),
                base_x=x1,
                fallback_x1=x1,
                fallback_x2=x2,
                component_boxes=component_boxes,
            )
            split_bbox = (split_x1, split_y1, max(1, split_x2 - split_x1), max(1, split_y2 - split_y1))
            if not component_boxes:
                component_boxes = self._component_boxes_for_split(line.component_boxes, split_bbox)
            split_lines.append(
                SegmentedLine(
                    order=line.order,
                    bbox=split_bbox,
                    component_boxes=component_boxes or (split_bbox,),
                    metadata={
                        **line.metadata,
                        "refined_split": True,
                        "refine_source": "local_projection",
                        "refine_split_index": split_index,
                        "refine_split_count": len(runs),
                        "token_count": len(component_boxes or (split_bbox,)),
                    },
                )
            )

        return split_lines or [line]

    def _projection_runs_from_mask(
        self,
        mask: np.ndarray,
        *,
        row_density: np.ndarray | None = None,
    ) -> list[tuple[int, int]]:
        if mask.size == 0:
            return []
        height, width = mask.shape[:2]
        if height <= 0 or width <= 0:
            return []
        density = (
            row_density.astype(np.float32, copy=False)
            if row_density is not None
            else mask.mean(axis=1).astype(np.float32)
        )
        density_peak = float(density.max()) if density.size else 0.0
        row_threshold = max(
            self.projection_threshold_ratio,
            min(0.18, density_peak * 0.35),
            1.0 / max(1, width),
        )
        active = density >= row_threshold
        active = self._fill_short_row_gaps(active)
        runs = [
            (start, end)
            for start, end in self._merge_runs(self._contiguous_runs(active))
            if end - start + 1 >= self.min_line_height_px
        ]
        components = self._extract_component_boxes(mask)
        return self._augment_runs_with_orphan_components(
            runs,
            component_boxes=components,
            content_width=width,
        )

    def _build_lines_from_runs(
        self,
        mask: np.ndarray,
        runs: list[tuple[int, int]],
        *,
        header_trim_px: int,
        metadata_factory: Callable[[int, tuple[int, int], int], dict[str, Any]],
    ) -> list[SegmentedLine]:
        if mask.size == 0 or not runs:
            return []

        content_height = int(mask.shape[0])
        content_width = int(mask.shape[1])
        boundaries = self._line_boundaries_from_runs(runs, content_height=content_height)
        components = self._extract_component_boxes(mask)
        lines: list[SegmentedLine] = []
        for order, ((start, end), (band_top, band_bottom)) in enumerate(zip(runs, boundaries, strict=False)):
            component_boxes = self._component_boxes_for_vertical_span(components, start, end + 1)
            x1, x2 = self._x_bounds_for_span(
                mask,
                span_top=band_top,
                span_bottom=band_bottom,
                content_width=content_width,
                base_x=0,
                fallback_x1=0,
                fallback_x2=content_width,
                component_boxes=component_boxes,
            )
            y1 = max(0, band_top)
            y2 = min(content_height, band_bottom)
            bbox = (x1, y1 + header_trim_px, max(1, x2 - x1), max(1, y2 - y1))
            lines.append(
                SegmentedLine(
                    order=order,
                    bbox=bbox,
                    component_boxes=tuple(
                        (cx, cy + header_trim_px, cw, ch) for cx, cy, cw, ch in component_boxes
                    ) or (bbox,),
                    metadata=metadata_factory(order, (start, end), len(runs)),
                )
            )
        return lines

    @staticmethod
    def _line_boundaries_from_runs(
        runs: list[tuple[int, int]],
        *,
        content_height: int,
    ) -> list[tuple[int, int]]:
        if not runs:
            return []

        boundaries: list[tuple[int, int]] = []
        for index, (start, end) in enumerate(runs):
            if index == 0:
                band_top = 0
            else:
                prev_end = runs[index - 1][1]
                band_top = int(np.floor((prev_end + start + 1) / 2.0))

            if index == len(runs) - 1:
                band_bottom = content_height
            else:
                next_start = runs[index + 1][0]
                band_bottom = int(np.ceil((end + next_start + 1) / 2.0))

            if band_bottom <= band_top:
                band_bottom = min(content_height, band_top + 1)
            boundaries.append((band_top, band_bottom))
        return boundaries

    @staticmethod
    def _component_boxes_for_split(
        component_boxes: tuple[tuple[int, int, int, int], ...],
        split_bbox: tuple[int, int, int, int],
    ) -> tuple[tuple[int, int, int, int], ...]:
        if not component_boxes:
            return ()

        _sx, sy, _sw, sh = split_bbox
        split_top = sy
        split_bottom = sy + sh
        selected = tuple(
            box
            for box in component_boxes
            if max(split_top, box[1]) < min(split_bottom, box[1] + box[3])
        )
        return selected

    def _extract_component_boxes(self, mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        if mask.size == 0:
            return []

        try:
            cv2: Any = importlib.import_module("cv2")
            mask_u8 = mask.astype(np.uint8, copy=False)
            component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
                mask_u8,
                connectivity=8,
            )
            boxes: list[tuple[int, int, int, int]] = []
            for index in range(1, int(component_count)):
                x = int(stats[index, cv2.CC_STAT_LEFT])
                y = int(stats[index, cv2.CC_STAT_TOP])
                w = int(stats[index, cv2.CC_STAT_WIDTH])
                h = int(stats[index, cv2.CC_STAT_HEIGHT])
                area = int(stats[index, cv2.CC_STAT_AREA])
                if w <= 0 or h <= 0 or area <= 0:
                    continue
                boxes.append((x, y, w, h))
            return boxes
        except ImportError:
            return []

    def _augment_runs_with_orphan_components(
        self,
        runs: list[tuple[int, int]],
        *,
        component_boxes: Sequence[tuple[int, int, int, int]],
        content_width: int,
    ) -> list[tuple[int, int]]:
        if not component_boxes:
            return runs

        orphan_components = [
            box
            for box in component_boxes
            if not any(max(box[1], start) <= min(box[1] + box[3] - 1, end) for start, end in runs)
        ]
        if not orphan_components:
            return runs

        rescued_runs: list[tuple[int, int]] = []
        for group in self._group_component_rows(orphan_components):
            min_y = min(box[1] for box in group)
            max_y = max(box[1] + box[3] - 1 for box in group)
            min_x = min(box[0] for box in group)
            max_x = max(box[0] + box[2] for box in group)
            total_area = sum(box[2] * box[3] for box in group)
            run_height = max_y - min_y + 1
            run_width = max_x - min_x
            if run_height < self.min_line_height_px:
                continue
            if len(group) < 2 and total_area < max(16, self.min_line_height_px * 6):
                continue
            if run_width < max(8, min(18, content_width // 20)):
                continue
            rescued_runs.append((min_y, max_y))

        if not rescued_runs:
            return runs

        combined = sorted([*runs, *rescued_runs], key=lambda item: (item[0], item[1]))
        coalesced: list[tuple[int, int]] = []
        for start, end in combined:
            if not coalesced or start > coalesced[-1][1]:
                coalesced.append((start, end))
                continue
            prev_start, prev_end = coalesced[-1]
            coalesced[-1] = (prev_start, max(prev_end, end))
        return coalesced

    def _group_component_rows(
        self,
        component_boxes: Sequence[tuple[int, int, int, int]],
    ) -> list[list[tuple[int, int, int, int]]]:
        if not component_boxes:
            return []

        rows: list[list[tuple[int, int, int, int]]] = []
        for box in sorted(component_boxes, key=lambda item: (item[1], item[0])):
            box_top = box[1]
            box_bottom = box[1] + box[3] - 1
            attached = False
            for row in rows:
                row_top = min(item[1] for item in row)
                row_bottom = max(item[1] + item[3] - 1 for item in row)
                gap = max(0, max(box_top - row_bottom - 1, row_top - box_bottom - 1))
                if gap <= self.merge_gap_px:
                    row.append(box)
                    attached = True
                    break
            if not attached:
                rows.append([box])
        return rows

    @staticmethod
    def _component_boxes_for_vertical_span(
        component_boxes: Sequence[tuple[int, int, int, int]],
        span_top: int,
        span_bottom: int,
    ) -> list[tuple[int, int, int, int]]:
        if span_bottom <= span_top:
            return []
        return [
            box
            for box in component_boxes
            if max(span_top, box[1]) < min(span_bottom, box[1] + box[3])
        ]

    def _x_bounds_for_span(
        self,
        mask: np.ndarray,
        *,
        span_top: int,
        span_bottom: int,
        content_width: int,
        base_x: int,
        fallback_x1: int,
        fallback_x2: int,
        component_boxes: Sequence[tuple[int, int, int, int]],
    ) -> tuple[int, int]:
        if component_boxes:
            x1 = min(box[0] for box in component_boxes)
            x2 = max(box[0] + box[2] for box in component_boxes)
            return (
                max(0, x1 - self.line_padding_px - self.extra_left_pad_px),
                min(content_width, x2 + self.line_padding_px),
            )

        band = mask[span_top:span_bottom, :]
        _ys, xs = np.where(band)
        if xs.size == 0:
            return fallback_x1, fallback_x2

        return (
            max(0, base_x + int(xs.min()) - self.line_padding_px - self.extra_left_pad_px),
            min(content_width, base_x + int(xs.max()) + self.line_padding_px + 1),
        )

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
