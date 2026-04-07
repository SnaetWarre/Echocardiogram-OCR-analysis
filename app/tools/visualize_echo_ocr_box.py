from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from matplotlib.lines import Line2D

from app.io.dicom_loader import load_dicom_series
from app.pipeline.echo_ocr_box_detector import (
    TopLeftBlueGrayBoxDetector,
    _MEASUREMENT_BOX_RGB,
    _MEASUREMENT_BOX_TOLERANCE,
    _color_match_mask,
    _to_gray,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quickly visualize the echo OCR measurement box detection and intermediate masks."
    )
    parser.add_argument("path", type=Path, help="Path to the DICOM file")
    parser.add_argument(
        "--frame",
        type=int,
        default=0,
        help="Frame index to inspect (default: 0)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=float(_MEASUREMENT_BOX_TOLERANCE),
        help=(
            f"Max absolute difference per R, G, B channel around target color "
            f"{tuple(_MEASUREMENT_BOX_RGB)}"
        ),
    )
    parser.add_argument(
        "--min-pixels",
        type=int,
        default=240,
        help="Minimum pixels required for a valid detection",
    )
    parser.add_argument(
        "--trim-top",
        type=int,
        default=0,
        help="Preview trimming this many pixels from the top of the detected ROI",
    )
    parser.add_argument(
        "--show-pixel-ruler",
        action="store_true",
        help="Overlay pixel ruler ticks on the detected ROI for manual measurement",
    )
    parser.add_argument(
        "--ruler-step",
        type=int,
        default=10,
        help="Pixel spacing between ruler ticks when --show-pixel-ruler is enabled",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Save the visualization to this path instead of only showing it interactively",
    )
    parser.add_argument(
        "--save-temp",
        action="store_true",
        help="Save the visualization to a temporary PNG file and print the path",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI used when saving the visualization",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reading invalid DICOM files",
    )
    return parser.parse_args()


def _ensure_rgb(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return np.stack([frame, frame, frame], axis=-1)
    if frame.ndim == 3 and frame.shape[-1] >= 3:
        return frame[..., :3]
    raise ValueError(f"Unsupported frame shape: {frame.shape}")


def _compute_debug_masks(
    frame: np.ndarray,
    *,
    box_color: tuple[int, int, int],
    tolerance: float,
) -> dict[str, np.ndarray]:
    search = frame
    rgb = _ensure_rgb(search)
    gray = _to_gray(search)

    rgb_i = rgb.astype(np.int16)[..., :3]
    tr, tg, tb = int(box_color[0]), int(box_color[1]), int(box_color[2])
    dr = np.abs(rgb_i[..., 0] - tr).astype(np.float32)
    dg = np.abs(rgb_i[..., 1] - tg).astype(np.float32)
    db = np.abs(rgb_i[..., 2] - tb).astype(np.float32)
    max_channel_abs_diff = np.maximum(np.maximum(dr, dg), db)
    color_mask = _color_match_mask(rgb.astype(np.int16), box_color, tolerance)
    refined_mask = np.zeros_like(color_mask, dtype=bool)

    try:
        import cv2

        flood = (color_mask.astype(np.uint8) * 255).copy()
        flood_mask = np.zeros((flood.shape[0] + 2, flood.shape[1] + 2), dtype=np.uint8)
        cv2.floodFill(flood, flood_mask, (0, 0), 255)
        holes = cv2.bitwise_not(flood)
        filled_mask = cv2.bitwise_or(color_mask.astype(np.uint8) * 255, holes)
        filled_mask_bool = filled_mask > 0

        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            filled_mask_bool.astype(np.uint8),
            connectivity=8,
        )

        if n_labels > 1:
            best_label = 0
            best_score = float("-inf")
            for label in range(1, n_labels):
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
                if width < height:
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

            if best_label > 0:
                refined_mask = labels == best_label
        else:
            refined_mask = filled_mask_bool
    except ImportError:
        filled_mask_bool = color_mask.copy()

    return {
        "search": search,
        "gray": gray,
        "max_channel_abs_diff": max_channel_abs_diff,
        "color_mask": color_mask,
        "filled_mask": filled_mask_bool,
        "refined_mask": refined_mask,
    }


def _draw_bbox(ax, bbox: tuple[int, int, int, int], *, color: str, label: str) -> None:
    x, y, w, h = bbox
    rect = patches.Rectangle(
        (x, y),
        w,
        h,
        linewidth=2,
        edgecolor=color,
        facecolor="none",
    )
    ax.add_patch(rect)
    ax.text(
        x,
        max(0, y - 3),
        label,
        color=color,
        fontsize=10,
        fontweight="bold",
        bbox={"facecolor": "black", "alpha": 0.55, "pad": 2},
    )


def _draw_trim_guide(
    ax,
    bbox: tuple[int, int, int, int],
    *,
    trim_top: int,
    color: str = "cyan",
) -> tuple[int, int, int, int] | None:
    x, y, w, h = bbox
    if trim_top <= 0 or trim_top >= h:
        return None

    trim_y = y + trim_top
    trimmed_bbox = (x, trim_y, w, h - trim_top)

    ax.add_line(
        Line2D(
            [x, x + w],
            [trim_y, trim_y],
            color=color,
            linewidth=2,
            linestyle="--",
        )
    )
    ax.text(
        x,
        min(y + h - 2, trim_y + 2),
        f"trim_top={trim_top}px",
        color=color,
        fontsize=9,
        fontweight="bold",
        bbox={"facecolor": "black", "alpha": 0.55, "pad": 2},
    )
    rect = patches.Rectangle(
        (trimmed_bbox[0], trimmed_bbox[1]),
        trimmed_bbox[2],
        trimmed_bbox[3],
        linewidth=2,
        edgecolor=color,
        facecolor="none",
        linestyle="--",
    )
    ax.add_patch(rect)
    return trimmed_bbox


def _draw_pixel_ruler(
    ax,
    bbox: tuple[int, int, int, int],
    *,
    step: int,
    color: str = "yellow",
) -> None:
    x, y, w, h = bbox
    if step <= 0:
        return

    for offset in range(0, w + 1, step):
        tick_x = x + offset
        ax.add_line(Line2D([tick_x, tick_x], [y, y - 5], color=color, linewidth=1.5))
        ax.text(
            tick_x,
            max(0, y - 7),
            str(offset),
            color=color,
            fontsize=7,
            ha="center",
            va="bottom",
            bbox={"facecolor": "black", "alpha": 0.4, "pad": 1},
        )

    for offset in range(0, h + 1, step):
        tick_y = y + offset
        ax.add_line(Line2D([x - 5, x], [tick_y, tick_y], color=color, linewidth=1.5))
        ax.text(
            max(0, x - 7),
            tick_y,
            str(offset),
            color=color,
            fontsize=7,
            ha="right",
            va="center",
            bbox={"facecolor": "black", "alpha": 0.4, "pad": 1},
        )


def _resolve_output_path(args: argparse.Namespace) -> Path | None:
    if args.save is not None:
        return args.save

    if args.save_temp:
        with tempfile.NamedTemporaryFile(prefix="echo_ocr_box_", suffix=".png", delete=False) as handle:
            return Path(handle.name)

    return None


def main() -> int:
    args = _parse_args()

    if not args.path.exists():
        print(f"File not found: {args.path}", file=sys.stderr)
        return 2

    series = load_dicom_series(args.path, load_pixels=True, force=args.force)
    if args.frame < 0 or args.frame >= series.frame_count:
        print(
            f"Frame index {args.frame} out of range for series with {series.frame_count} frame(s).",
            file=sys.stderr,
        )
        return 2

    output_path = _resolve_output_path(args)

    frame = series.get_frame(args.frame)
    detector = TopLeftBlueGrayBoxDetector(
        min_pixels=args.min_pixels,
        box_color=_MEASUREMENT_BOX_RGB,
        color_tolerance=args.tolerance,
    )
    detection = detector.detect(frame)

    debug = _compute_debug_masks(
        frame,
        box_color=_MEASUREMENT_BOX_RGB,
        tolerance=args.tolerance,
    )

    rgb_frame = _ensure_rgb(frame)
    search_rgb = _ensure_rgb(debug["search"])
    search_bbox = (0, 0, rgb_frame.shape[1], rgb_frame.shape[0])

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(
        f"Echo OCR Box Visualization\n"
        f"{args.path.name} | frame={args.frame} | "
        f"target_rgb={tuple(_MEASUREMENT_BOX_RGB)} | tolerance={args.tolerance} | "
        f"trim_top={args.trim_top}px",
        fontsize=14,
    )

    ax = axes[0, 0]
    ax.imshow(rgb_frame)
    ax.set_title("Full frame")
    _draw_bbox(ax, search_bbox, color="yellow", label="search region")
    if detection.present and detection.bbox is not None:
        _draw_bbox(ax, detection.bbox, color="lime", label="detected ROI")
        if args.show_pixel_ruler:
            _draw_pixel_ruler(ax, detection.bbox, step=args.ruler_step)
        _draw_trim_guide(ax, detection.bbox, trim_top=args.trim_top)
    ax.axis("off")

    ax = axes[0, 1]
    ax.imshow(search_rgb)
    ax.set_title("Full-frame detector search")
    if detection.present and detection.bbox is not None:
        x, y, w, h = detection.bbox
        _draw_bbox(ax, (x, y, w, h), color="lime", label="detected ROI")
        if args.show_pixel_ruler:
            _draw_pixel_ruler(ax, detection.bbox, step=args.ruler_step)
        _draw_trim_guide(ax, detection.bbox, trim_top=args.trim_top)
    ax.axis("off")

    ax = axes[0, 2]
    im = ax.imshow(debug["max_channel_abs_diff"], cmap="viridis")
    ax.set_title("Max |ΔR|, |ΔG|, |ΔB| vs target")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    ax.imshow(debug["color_mask"], cmap="gray")
    ax.set_title("Initial color mask")
    ax.axis("off")

    ax = axes[1, 1]
    ax.imshow(debug["filled_mask"], cmap="gray")
    ax.set_title("Hole-filled color mask")
    ax.axis("off")

    ax = axes[1, 2]
    ax.imshow(debug["refined_mask"], cmap="gray")
    title = "Largest connected component"
    if detection.present and detection.bbox is not None:
        x, y, w, h = detection.bbox
        title += f"\nBBox=({x}, {y}, {w}, {h}) conf={detection.confidence:.3f}"
        if args.trim_top > 0:
            trimmed_height = max(0, h - args.trim_top)
            title += f"\nTrimmed OCR bbox=({x}, {y + args.trim_top}, {w}, {trimmed_height})"
    else:
        title += "\nNo detection"
    ax.set_title(title)
    ax.axis("off")

    plt.tight_layout()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=args.dpi, bbox_inches="tight")
        print(f"Saved visualization: {output_path}")

    plt.show()

    if detection.present and detection.bbox is not None:
        x, y, w, h = detection.bbox
        print(
            f"Detected ROI: x={x}, y={y}, width={w}, height={h}, confidence={detection.confidence:.4f}"
        )
        if args.trim_top > 0:
            trimmed_height = max(0, h - args.trim_top)
            print(
                f"Trimmed OCR ROI preview: x={x}, y={y + args.trim_top}, width={w}, height={trimmed_height}"
            )
    else:
        print("No ROI detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
