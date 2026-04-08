"""Scan label JSON DICOMs: report where TopLeftBlueGrayBoxDetector never finds a panel ROI."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.layout.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.validation.datasets import DEFAULT_LABELS_PATH, parse_labels, parse_requested_splits  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default=str(DEFAULT_LABELS_PATH), help="exact_lines.json path")
    ap.add_argument(
        "--split",
        default="",
        help="Comma-separated splits (empty = all splits)",
    )
    args = ap.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.is_file():
        raise SystemExit(f"Labels not found: {labels_path}")

    split_filter = parse_requested_splits(args.split)
    files = parse_labels(labels_path, split_filter=split_filter if split_filter else None)
    detector = TopLeftBlueGrayBoxDetector()

    print(
        "TopLeftBlueGrayBoxDetector expects each RGB channel within the tolerance (default ±6) of "
        "#1A2129, enough area (>=240 px), top-left region (left<=220, top<=120), "
        "and width>=height, width>=40, height>=12. Grayscale / wrong overlay color / "
        "box elsewhere fails.\n"
    )

    no_roi: list[tuple[str, str, str, int]] = []
    ok: list[tuple[str, str, int, int, float]] = []

    for lf in files:
        if not lf.path.exists():
            print(f"MISSING FILE  [{lf.split}] {lf.file_name}\n  path={lf.path}")
            continue
        try:
            series = load_dicom_series(lf.path, load_pixels=True)
        except Exception as exc:
            print(f"LOAD ERROR  [{lf.split}] {lf.file_name}: {exc}")
            continue

        n_frames = series.frame_count
        roi_hits = 0
        best_conf = 0.0
        for idx in range(n_frames):
            frame = series.get_frame(idx)
            det = detector.detect(frame)
            if det.present and det.bbox is not None:
                roi_hits += 1
                best_conf = max(best_conf, det.confidence)

        if roi_hits == 0:
            no_roi.append((lf.file_name, lf.split, str(lf.path.resolve()), n_frames))
        else:
            ok.append((lf.file_name, lf.split, n_frames, roi_hits, best_conf))

    print(f"Scanned {len(files)} label entries ({len(ok)} with ROI on ≥1 frame, {len(no_roi)} never).\n")
    print("--- Files with NO panel ROI on any frame (OCR pipeline gets no crop) ---")
    if not no_roi:
        print("  (none)")
    for name, split, path, n_frames in no_roi:
        print(f"  [{split}] {name}  frames={n_frames}")
        print(f"    {path}")

    print("\n--- Sample OK files (first 5) ---")
    for row in ok[:5]:
        name, split, nf, hits, conf = row
        print(f"  [{split}] {name}  frames={nf} roi_frames={hits} best_conf={conf:.3f}")


if __name__ == "__main__":
    main()
