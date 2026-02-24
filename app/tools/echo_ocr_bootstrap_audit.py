from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_pipeline import TopLeftBlueGrayBoxDetector  # noqa: E402


@dataclass(frozen=True)
class ManifestRow:
    dicom_path: str
    frame_index: int
    detector_present: bool
    detector_confidence: float
    roi_bbox: str


def iter_dicom_files(root: Path, pattern: str) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in root.rglob(pattern):
        if path.is_file():
            yield path


def build_manifest(root: Path, pattern: str, max_files: int = 0) -> List[ManifestRow]:
    detector = TopLeftBlueGrayBoxDetector()
    rows: List[ManifestRow] = []
    files = list(iter_dicom_files(root, pattern))
    if max_files > 0:
        files = files[:max_files]
    for path in files:
        series = load_dicom_series(path, load_pixels=False)
        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            detection = detector.detect(frame)
            bbox = ""
            if detection.bbox:
                bbox = ",".join(str(v) for v in detection.bbox)
            rows.append(
                ManifestRow(
                    dicom_path=str(path),
                    frame_index=frame_index,
                    detector_present=detection.present,
                    detector_confidence=detection.confidence,
                    roi_bbox=bbox,
                )
            )
    return rows


def stratified_sample(rows: List[ManifestRow], positives: int, negatives: int, seed: int) -> List[ManifestRow]:
    rng = random.Random(seed)
    pos_pool = [row for row in rows if row.detector_present]
    neg_pool = [row for row in rows if not row.detector_present]
    rng.shuffle(pos_pool)
    rng.shuffle(neg_pool)
    return pos_pool[:positives] + neg_pool[:negatives]


def write_manifest(path: Path, rows: List[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ManifestRow.__annotations__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_annotation_template(path: Path, rows: List[ManifestRow]) -> None:
    fields = [
        "dicom_path",
        "frame_index",
        "box_present",
        "ocr_readable",
        "measurement_name",
        "measurement_value",
        "measurement_unit",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "dicom_path": row.dicom_path,
                    "frame_index": row.frame_index,
                    "box_present": "",
                    "ocr_readable": "",
                    "measurement_name": "",
                    "measurement_value": "",
                    "measurement_unit": "",
                    "notes": "",
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bootstrap audit manifests for echocardiogram OCR.")
    parser.add_argument("root", type=Path, help="DICOM directory or single file")
    parser.add_argument("--pattern", type=str, default="*.dcm")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--positives", type=int, default=200)
    parser.add_argument("--negatives", type=int, default=100)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/ocr-audit"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = build_manifest(args.root, args.pattern, max_files=args.max_files)
    if not rows:
        print("No frames found.")
        return 1
    sampled = stratified_sample(rows, args.positives, args.negatives, args.seed)
    manifest_path = args.out_dir / "audit_manifest.csv"
    annotation_path = args.out_dir / "audit_annotations_template.csv"
    write_manifest(manifest_path, sampled)
    write_annotation_template(annotation_path, sampled)
    print(f"Manifest: {manifest_path}")
    print(f"Annotation template: {annotation_path}")
    print(f"Rows sampled: {len(sampled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
