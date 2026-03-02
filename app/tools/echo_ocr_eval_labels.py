"""Evaluate the echo-OCR pipeline against the hand-labelled ground truth in labels.md.

Usage (from project root):
    python -m app.tools.echo_ocr_eval_labels [--engine ENGINE] [--all-engines]

The script:
  1. Parses labels.md to extract (path, measurements) pairs.
  2. For each DICOM, runs the pipeline with the specified engine(s).
  3. Compares predicted measurements to ground truth.
  4. Reports per-file and aggregate accuracy.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline, preprocess_roi  # noqa: E402
from app.pipeline.measurement_parsers import RegexMeasurementParser  # noqa: E402
from app.pipeline.ocr_engines import (  # noqa: E402
    OcrEngine,
    OcrResult,
    build_engine,
)


# ---------------------------------------------------------------------------
# Label parsing
# ---------------------------------------------------------------------------

@dataclass
class LabeledMeasurement:
    name: str
    value: str
    unit: str | None


@dataclass
class LabeledFile:
    path: Path
    measurements: list[LabeledMeasurement] = field(default_factory=list)


_LABEL_RE = re.compile(
    r"->\s*(?P<name>.+?)\s+(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)?",
    flags=re.IGNORECASE,
)


def parse_labels(labels_path: Path) -> list[LabeledFile]:
    """Parse the labels.md file into structured LabeledFile entries."""
    text = labels_path.read_text(encoding="utf-8")
    blocks = re.split(r"^--\s*$", text, flags=re.MULTILINE)
    results: list[LabeledFile] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        path_match = re.search(r"path:\s*(.+)", block)
        if path_match is None:
            continue
        raw_path = path_match.group(1).strip()
        # Fix paths ending in .Documents (typo in labels)
        if raw_path.endswith(".Documents"):
            raw_path = raw_path.rsplit(".", 1)[0] + ".dcm"
        file_path = Path(raw_path)
        measurements: list[LabeledMeasurement] = []
        for line in block.splitlines():
            m = _LABEL_RE.search(line)
            if m is None:
                continue
            name = m.group("name").strip()
            value = m.group("value").replace(",", ".")
            unit = m.group("unit")
            measurements.append(LabeledMeasurement(name=name, value=value, unit=unit))
        if measurements:
            results.append(LabeledFile(path=file_path, measurements=measurements))
    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Normalize measurement name/value for fuzzy comparison."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _values_match(predicted: str, expected: str) -> bool:
    """Check if two numeric values match, allowing minor float tolerance."""
    try:
        return abs(float(predicted) - float(expected)) < 0.011
    except ValueError:
        return predicted.strip() == expected.strip()


@dataclass
class MatchResult:
    label_name: str
    label_value: str
    label_unit: str | None
    predicted_name: str | None
    predicted_value: str | None
    predicted_unit: str | None
    name_match: bool
    value_match: bool
    unit_match: bool
    full_match: bool


def score_predictions(
    labels: list[LabeledMeasurement],
    predictions: list[dict[str, str | None]],
) -> list[MatchResult]:
    """Score predictions against ground truth labels."""
    results: list[MatchResult] = []
    used_preds: set[int] = set()

    for label in labels:
        best_match: MatchResult | None = None
        best_idx: int | None = None

        for idx, pred in enumerate(predictions):
            if idx in used_preds:
                continue
            pred_name = pred.get("name", "") or ""
            pred_value = pred.get("value", "") or ""
            pred_unit = pred.get("unit")

            name_match = _normalize(label.name) in _normalize(pred_name) or _normalize(pred_name) in _normalize(label.name)
            value_match = _values_match(pred_value, label.value)
            unit_match = (label.unit is None and pred_unit is None) or (
                label.unit is not None and pred_unit is not None and label.unit.lower() == pred_unit.lower()
            )
            full_match = name_match and value_match and unit_match

            if full_match:
                best_match = MatchResult(
                    label_name=label.name,
                    label_value=label.value,
                    label_unit=label.unit,
                    predicted_name=pred_name,
                    predicted_value=pred_value,
                    predicted_unit=pred_unit,
                    name_match=True,
                    value_match=True,
                    unit_match=True,
                    full_match=True,
                )
                best_idx = idx
                break
            elif value_match and (best_match is None or not best_match.value_match):
                best_match = MatchResult(
                    label_name=label.name,
                    label_value=label.value,
                    label_unit=label.unit,
                    predicted_name=pred_name,
                    predicted_value=pred_value,
                    predicted_unit=pred_unit,
                    name_match=name_match,
                    value_match=True,
                    unit_match=unit_match,
                    full_match=False,
                )
                best_idx = idx

        if best_match is not None and best_idx is not None:
            used_preds.add(best_idx)
            results.append(best_match)
        else:
            results.append(
                MatchResult(
                    label_name=label.name,
                    label_value=label.value,
                    label_unit=label.unit,
                    predicted_name=None,
                    predicted_value=None,
                    predicted_unit=None,
                    name_match=False,
                    value_match=False,
                    unit_match=False,
                    full_match=False,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_evaluation(
    labels: list[LabeledFile],
    engine: OcrEngine,
    *,
    verbose: bool = True,
    args=None
) -> dict[str, float]:
    """Run the pipeline on all labeled files and compute scores."""
    detector = TopLeftBlueGrayBoxDetector()
    from app.pipeline.measurement_parsers import build_parser
    parser = build_parser(args.parser)

    total_labels = 0
    total_full_match = 0
    total_value_match = 0
    total_name_match = 0
    total_detected = 0
    total_files = 0
    total_files_with_detections = 0
    elapsed_total = 0.0

    for labeled_file in labels:
        if not labeled_file.path.exists():
            if verbose:
                print(f"  ⚠ SKIP (file not found): {labeled_file.path.name}")
            continue

        total_files += 1
        start = time.perf_counter()

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception as exc:
            if verbose:
                print(f"  ✗ LOAD ERROR: {labeled_file.path.name}: {exc}")
            total_labels += len(labeled_file.measurements)
            continue

        # Run OCR on all frames, collect all predictions
        all_predictions: list[dict[str, str | None]] = []
        raw_ocr_texts: list[str] = []

        for frame_idx in range(series.frame_count):
            frame = series.get_frame(frame_idx)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                continue

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            prepared = preprocess_roi(roi)
            ocr_result = engine.extract(prepared)
            raw_ocr_texts.append(ocr_result.text)

            measurements = parser.parse(ocr_result.text, confidence=ocr_result.confidence)
            for m in measurements:
                all_predictions.append({"name": m.name, "value": m.value, "unit": m.unit})

        elapsed = time.perf_counter() - start
        elapsed_total += elapsed

        if all_predictions:
            total_files_with_detections += 1

        # Score
        match_results = score_predictions(labeled_file.measurements, all_predictions)
        n_labels = len(labeled_file.measurements)
        n_full = sum(1 for r in match_results if r.full_match)
        n_value = sum(1 for r in match_results if r.value_match)
        n_name = sum(1 for r in match_results if r.name_match)

        total_labels += n_labels
        total_full_match += n_full
        total_value_match += n_value
        total_name_match += n_name
        total_detected += len(all_predictions)

        if verbose:
            status = "✓" if n_full == n_labels else "◐" if n_full > 0 else "✗"
            print(
                f"  {status} {labeled_file.path.name}: "
                f"{n_full}/{n_labels} full, {n_value}/{n_labels} value, "
                f"{len(all_predictions)} preds, {elapsed:.1f}s"
            )
            # Show OCR text for debugging
            if raw_ocr_texts and n_full < n_labels:
                unique_texts = set()
                for t in raw_ocr_texts:
                    cleaned = " ".join(t.split())
                    if cleaned and cleaned not in unique_texts:
                        unique_texts.add(cleaned)
                        if len(unique_texts) <= 3:
                            print(f"    OCR: {cleaned[:120]}")

            for r in match_results:
                if not r.full_match:
                    pred_str = f"→ {r.predicted_name} {r.predicted_value} {r.predicted_unit}" if r.predicted_name else "→ NOT FOUND"
                    print(f"    MISS: {r.label_name} {r.label_value} {r.label_unit} {pred_str}")

    # Aggregate scores
    scores = {
        "total_labels": float(total_labels),
        "total_full_match": float(total_full_match),
        "total_value_match": float(total_value_match),
        "total_name_match": float(total_name_match),
        "total_predicted": float(total_detected),
        "total_files": float(total_files),
        "total_files_with_detections": float(total_files_with_detections),
        "full_match_rate": total_full_match / max(total_labels, 1),
        "value_match_rate": total_value_match / max(total_labels, 1),
        "name_match_rate": total_name_match / max(total_labels, 1),
        "detection_rate": total_files_with_detections / max(total_files, 1),
        "elapsed_s": elapsed_total,
    }
    return scores


def _print_summary(engine_name: str, scores: dict[str, float]) -> None:
    total = int(scores["total_labels"])
    full = int(scores["total_full_match"])
    value = int(scores["total_value_match"])
    name = int(scores["total_name_match"])
    preds = int(scores["total_predicted"])
    files = int(scores["total_files"])
    detected = int(scores["total_files_with_detections"])

    print(f"\n{'=' * 60}")
    print(f"  Engine: {engine_name}")
    print(f"  Files evaluated:       {files}")
    print(f"  Files with detections: {detected} ({scores['detection_rate']:.0%})")
    print(f"  Total labels:          {total}")
    print(f"  Total predictions:     {preds}")
    print(f"  Full matches:          {full}/{total} ({scores['full_match_rate']:.1%})")
    print(f"  Value matches:         {value}/{total} ({scores['value_match_rate']:.1%})")
    print(f"  Name matches:          {name}/{total} ({scores['name_match_rate']:.1%})")
    print(f"  Elapsed time:          {scores['elapsed_s']:.1f}s")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate echo OCR pipeline against labels")
    parser.add_argument("--engine", default="easyocr", help="OCR engine to use (tesseract, easyocr, paddleocr)")
    parser.add_argument("--all-engines", action="store_true", help="Run evaluation with all available engines")
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels.md"), help="Path to labels.md")
    parser.add_argument("--parser", default="regex", help="Parser mode (regex, local_llm, hybrid)")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        print(f"Labels file not found: {labels_path}")
        sys.exit(1)

    labeled_files = parse_labels(labels_path)
    print(f"Parsed {len(labeled_files)} labeled files with {sum(len(f.measurements) for f in labeled_files)} total measurements\n")

    engines_to_test: list[str] = []
    if args.all_engines:
        engines_to_test = ["easyocr", "tesseract", "paddleocr"]
    else:
        engines_to_test = [args.engine]

    for engine_name in engines_to_test:
        try:
            engine = build_engine(engine_name)
        except Exception as exc:
            print(f"\n⚠ Engine '{engine_name}' unavailable: {exc}")
            continue

        print(f"\n--- Evaluating with: {engine_name} ---")
        scores = run_evaluation(labeled_files, engine, verbose=True, args=args)
        _print_summary(engine_name, scores)


if __name__ == "__main__":
    main()
