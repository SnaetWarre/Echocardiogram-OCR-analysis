from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.pipeline.line_segmenter import DEFAULT_HEADER_TRIM_PX, LineSegmenter  # noqa: E402
from app.pipeline.line_transcriber import crop_segment  # noqa: E402
from app.repo_paths import (  # noqa: E402
    DEFAULT_EXACT_LINES_PATH,
    DEFAULT_LINE_RECOGNIZER_CROPS_DIR,
    DEFAULT_LINE_RECOGNIZER_MANIFEST_PATH,
)
from app.validation.datasets import parse_labels  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export line crops and manifest for line recognizer training")
    parser.add_argument("--labels", default=str(DEFAULT_EXACT_LINES_PATH))
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_LINE_RECOGNIZER_MANIFEST_PATH),
    )
    parser.add_argument(
        "--crops-dir",
        default=str(DEFAULT_LINE_RECOGNIZER_CROPS_DIR),
    )
    parser.add_argument("--split", default="", help="Optional comma separated split filter")
    parser.add_argument("--max-files", type=int, default=0, help="Optional file limit for quick exports")
    parser.add_argument(
        "--strict-count-match",
        action="store_true",
        help="Skip files where segmented line count does not match labeled line count",
    )
    args = parser.parse_args()

    split_filter = {item.strip().lower() for item in args.split.split(",") if item.strip()}
    labeled_files = parse_labels(Path(args.labels), split_filter=split_filter)
    if args.max_files > 0:
        labeled_files = labeled_files[: args.max_files]

    detector = TopLeftBlueGrayBoxDetector()
    segmenter = LineSegmenter(default_header_trim_px=DEFAULT_HEADER_TRIM_PX)
    manifest_path = Path(args.manifest)
    crops_dir = Path(args.crops_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0
    with manifest_path.open("w", encoding="utf-8") as handle:
        for labeled_file in labeled_files:
            if not labeled_file.path.exists():
                skipped += 1
                continue
            try:
                series = load_dicom_series(labeled_file.path, load_pixels=True)
            except Exception:
                skipped += 1
                continue
            if series.frame_count <= 0:
                skipped += 1
                continue

            frame = series.get_frame(0)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                skipped += 1
                continue

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            segmentation = segmenter.segment(roi)
            lines = sorted(segmentation.lines, key=lambda item: item.order)
            expected = sorted(
                labeled_file.measurements,
                key=lambda item: item.order if item.order is not None else 10_000,
            )
            if args.strict_count_match and len(lines) != len(expected):
                skipped += 1
                continue

            pair_count = min(len(lines), len(expected))
            if pair_count == 0:
                skipped += 1
                continue

            for index in range(pair_count):
                segment = lines[index]
                measurement = expected[index]
                crop = crop_segment(roi, segment)
                if crop.size == 0:
                    continue
                crop_path = crops_dir / f"{labeled_file.path.stem}__line_{index + 1:02d}.png"
                cv2.imwrite(str(crop_path), crop)
                payload = {
                    "image_path": str(crop_path),
                    "text": measurement.text,
                    "split": labeled_file.split,
                    "file_name": labeled_file.file_name,
                    "file_path": str(labeled_file.path),
                    "frame_index": 0,
                    "order": measurement.order if measurement.order is not None else index + 1,
                    "roi_bbox": [x, y, bw, bh],
                    "line_bbox": list(segment.bbox),
                    "segmentation_header_trim_px": segmentation.header_trim_px,
                }
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
                exported += 1

    print(f"Exported {exported} line crops to {crops_dir}")
    print(f"Wrote manifest to {manifest_path}")
    print(f"Skipped {skipped} files")


if __name__ == "__main__":
    main()
