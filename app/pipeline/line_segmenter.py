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
        segmentation_mode: str = "fixed_pitch",
        target_line_height_px: float = 20.0,
        default_header_trim_px: int = DEFAULT_HEADER_TRIM_PX,
        projection_threshold_ratio: float = 0.012,
        min_line_height_px: int = 4,
        line_padding_px: int = 2,
        merge_gap_px: int = 3,
        max_header_fraction: float = 0.45,
        refine_split_min_height_px: int = 10,
    ) -> None:
        self.segmentation_mode = str(segmentation_mode).strip().lower() or "fixed_pitch"
        self.target_line_height_px = max(1.0, float(target_line_height_px))
        self.default_header_trim_px = max(0, int(default_header_trim_px))
        self.projection_threshold_ratio = max(0.001, float(projection_threshold_ratio))
        self.min_line_height_px = max(1, int(min_line_height_px))
        self.line_padding_px = max(0, int(line_padding_px))
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

        if self.segmentation_mode == "fixed_pitch":
            lines = self._segment_fixed_pitch(content, header_trim_px=header_trim_px)
            if not lines and content.size > 0:
                lines = [
                    SegmentedLine(
                        order=0,
                        bbox=(0, header_trim_px, int(content.shape[1]), int(content.shape[0])),
                        component_boxes=((0, header_trim_px, int(content.shape[1]), int(content.shape[0])),),
                        metadata={
                            "source": "fixed_pitch",
                            "recovered": True,
                            "reason": "empty_fixed_pitch_segmentation",
                            "target_line_height_px": self.target_line_height_px,
                        },
                    )
                ]
            return SegmentationResult(
                header_trim_px=header_trim_px,
                content_bbox=content_bbox,
                lines=tuple(lines),
                used_token_boxes=False,
                used_projection_fallback=False,
                debug={
                    "line_count": len(lines),
                    "header_trim_px": header_trim_px,
                    "refined_line_splits": 0,
                    "segmentation_mode": self.segmentation_mode,
                    "target_line_height_px": self.target_line_height_px,
                    "estimated_line_count": len(lines),
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
            },
        )

    def _segment_fixed_pitch(self, content: np.ndarray, *, header_trim_px: int) -> list[SegmentedLine]:
        if content.size == 0:
            return []

        content_height = int(content.shape[0])
        content_width = int(content.shape[1])
        estimated_line_count = self._estimate_line_count(content_height)
        if estimated_line_count <= 0:
            return []

        stripe_edges = self._stripe_edges(content_height, estimated_line_count)
        lines: list[SegmentedLine] = []
        mask = self._text_mask(content)

        for order, (start, end) in enumerate(zip(stripe_edges[:-1], stripe_edges[1:], strict=False)):
            if end <= start:
                continue
            band = mask[start:end, :]
            _ys, xs = np.where(band)
            band_has_text = bool(xs.size)
            if xs.size == 0:
                x1 = 0
                x2 = content_width
            else:
                x1 = max(0, int(xs.min()) - self.line_padding_px)
                x2 = min(content_width, int(xs.max()) + self.line_padding_px + 1)
            y1 = start + header_trim_px
            y2 = end + header_trim_px
            line_bbox = (x1, y1, max(1, x2 - x1), max(1, y2 - y1))
            lines.append(
                SegmentedLine(
                    order=order,
                    bbox=line_bbox,
                    component_boxes=(line_bbox,),
                    metadata={
                        "source": "fixed_pitch",
                        "target_line_height_px": self.target_line_height_px,
                        "estimated_line_count": estimated_line_count,
                        "stripe_index": order,
                        "recovered": not band_has_text,
                        "reason": "empty_fixed_pitch_band" if not band_has_text else "",
                    },
                )
            )
        return lines

    def _estimate_line_count(self, content_height: int) -> int:
        if content_height <= 0:
            return 0
        estimated = int(np.floor((float(content_height) / self.target_line_height_px) + 0.5))
        return max(1, min(content_height, estimated))

    @staticmethod
    def _stripe_edges(content_height: int, line_count: int) -> list[int]:
        if content_height <= 0:
            return [0]
        if line_count <= 1:
            return [0, content_height]
        edges = np.rint(np.linspace(0.0, float(content_height), line_count + 1)).astype(int).tolist()
        edges[0] = 0
        edges[-1] = content_height
        for index in range(1, len(edges) - 1):
            edges[index] = max(edges[index], edges[index - 1] + 1)
        for index in range(len(edges) - 2, 0, -1):
            edges[index] = min(edges[index], edges[index + 1] - 1)
        return edges

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
            x1 = max(0, min(item[0] for item in row) - self.line_padding_px)
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

        boundaries: list[tuple[int, int]] = []
        for index, (start, end) in enumerate(runs):
            prev_end = runs[index - 1][1] if index > 0 else None
            next_start = runs[index + 1][0] if index + 1 < len(runs) else None
            top_pad = 0
            if prev_end is None:
                top_pad = min(self.line_padding_px, start)
            else:
                gap = max(0, start - prev_end - 1)
                top_pad = min(self.line_padding_px, gap // 2)
            bottom_pad = 0
            if next_start is None:
                bottom_pad = min(self.line_padding_px, max(0, crop.shape[0] - end - 1))
            else:
                gap = max(0, next_start - end - 1)
                bottom_pad = min(self.line_padding_px, gap // 2)
            band_top = max(0, start - top_pad)
            band_bottom = min(int(crop.shape[0]), end + bottom_pad + 1)
            boundaries.append((band_top, band_bottom))

        split_lines: list[SegmentedLine] = []
        for split_index, ((start, end), (band_top, band_bottom)) in enumerate(zip(runs, boundaries, strict=False)):
            band = mask[band_top:band_bottom, :]
            _ys, xs = np.where(band)
            if xs.size == 0:
                split_x1 = x1
                split_x2 = x2
            else:
                split_x1 = max(0, x1 + int(xs.min()) - self.line_padding_px)
                split_x2 = min(int(gray.shape[1]), x1 + int(xs.max()) + self.line_padding_px + 1)
            split_y1 = max(0, y1 + band_top)
            split_y2 = min(int(gray.shape[0]), y1 + band_bottom)
            split_bbox = (split_x1, split_y1, max(1, split_x2 - split_x1), max(1, split_y2 - split_y1))
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
