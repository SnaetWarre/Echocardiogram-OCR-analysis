from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_pipeline import TopLeftBlueGrayBoxDetector, preprocess_roi  # noqa: E402
from app.pipeline.measurement_parsers import RegexMeasurementParser  # noqa: E402
from app.pipeline.ocr_engines import UnavailableOcrEngineError, build_engine  # noqa: E402


@dataclass(frozen=True)
class BenchRow:
    dicom_path: str
    frame_index: int
    engine: str
    latency_ms: float
    ocr_confidence: float
    parsed_measurements: int
    text_preview: str


def iter_dicom_files(root: Path, pattern: str) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in root.rglob(pattern):
        if path.is_file():
            yield path


def collect_candidate_rois(root: Path, max_frames: int, pattern: str) -> List[Tuple[Path, int, object]]:
    detector = TopLeftBlueGrayBoxDetector()
    collected: List[Tuple[Path, int, object]] = []
    for path in iter_dicom_files(root, pattern):
        series = load_dicom_series(path, load_pixels=False)
        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            detection = detector.detect(frame)
            if not detection.present or not detection.bbox:
                continue
            x, y, w, h = detection.bbox
            roi = frame[y : y + h, x : x + w]
            collected.append((path, frame_index, preprocess_roi(roi)))
            if len(collected) >= max_frames:
                return collected
    return collected


def run_benchmark(rois: List[Tuple[Path, int, object]], engines: List[str]) -> List[BenchRow]:
    parser = RegexMeasurementParser()
    rows: List[BenchRow] = []
    for engine_name in engines:
        try:
            engine = build_engine(engine_name)
        except (UnavailableOcrEngineError, ValueError) as exc:
            print(f"[warn] skipping {engine_name}: {exc}")
            continue
        for path, frame_index, roi in rois:
            start = time.perf_counter()
            result = engine.extract(roi)
            elapsed = (time.perf_counter() - start) * 1000.0
            parsed = parser.parse(result.text, confidence=result.confidence)
            rows.append(
                BenchRow(
                    dicom_path=str(path),
                    frame_index=frame_index,
                    engine=engine_name,
                    latency_ms=elapsed,
                    ocr_confidence=result.confidence,
                    parsed_measurements=len(parsed),
                    text_preview=result.text[:120],
                )
            )
    return rows


def summarize(rows: List[BenchRow]) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = {}
    engines = sorted({row.engine for row in rows})
    for engine in engines:
        chunk = [row for row in rows if row.engine == engine]
        summary[engine] = {
            "samples": float(len(chunk)),
            "latency_ms_avg": statistics.mean(row.latency_ms for row in chunk),
            "ocr_confidence_avg": statistics.mean(row.ocr_confidence for row in chunk),
            "parsed_measurements_avg": statistics.mean(row.parsed_measurements for row in chunk),
        }
    return summary


def write_rows(rows: List[BenchRow], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BenchRow.__annotations__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark OCR engines on detected echocardiogram ROI boxes.")
    parser.add_argument("root", type=Path, help="DICOM file or directory")
    parser.add_argument("--pattern", type=str, default="*.dcm")
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--engines", type=str, default="paddleocr,tesseract,easyocr")
    parser.add_argument("--out-csv", type=Path, default=Path("artifacts/ocr-benchmark/results.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rois = collect_candidate_rois(args.root, max_frames=args.max_frames, pattern=args.pattern)
    if not rois:
        print("No candidate measurement ROI frames found.")
        return 1
    engines = [name.strip() for name in args.engines.split(",") if name.strip()]
    rows = run_benchmark(rois, engines=engines)
    if not rows:
        print("No benchmark rows produced. Install at least one configured OCR engine.")
        return 2
    write_rows(rows, args.out_csv)
    print(json.dumps(summarize(rows), indent=2))
    print(f"Saved benchmark rows to: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
