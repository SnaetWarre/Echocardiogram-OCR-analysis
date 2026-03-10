"""Evaluate the echo-OCR pipeline against a canonical JSON exact-line dataset.

Usage (from project root):
    python -m app.tools.echo_ocr_eval_labels --labels labels/exact_lines.json --split validation --engine surya

Dataset format:
{
  "version": 1,
  "task": "exact_roi_measurement_transcription",
  "files": [
    {
      "file_name": "94106955_0016.dcm",
      "file_path": "database_stage/files/p10/p10002221/s94106955/94106955_0016.dcm",
      "split": "validation",
      "measurements": [
        {"order": 1, "text": "1 IVSd 0.9 cm"},
        {"order": 2, "text": "2 LVIDd 5.4 cm"},
        {"order": 3, "text": "3 LVPWd 1.0 cm"}
      ]
    }
  ]
}

This evaluator treats the human-authored exact displayed line as the primary ground truth.
Structured parsing remains a secondary/derived representation used only for auxiliary metrics.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.pipeline.echo_ocr_pipeline import preprocess_roi  # noqa: E402
from app.pipeline.ocr_engines import OcrEngine, build_engine  # noqa: E402


DATASET_VERSION = 1
DATASET_TASK = "exact_roi_measurement_transcription"
DEFAULT_LABELS_PATH = PROJECT_ROOT / "labels" / "exact_lines.json"
HEADER_TRIM_PX = 14
_LINE_PARSE_RE = re.compile(
    r"""
    ^
    (?:(?P<prefix>\d+)\s+)?
    (?P<label>.*?)
    (?:
        \s+(?P<value>[-+]?\d+(?:[.,]\d+)?)
        (?:\s*(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2))?
    )?
    $
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Dataset models
# ---------------------------------------------------------------------------


@dataclass
class LabeledMeasurement:
    text: str
    order: int | None = None


@dataclass
class LabeledFile:
    path: Path
    file_name: str
    split: str
    measurements: list[LabeledMeasurement] = field(default_factory=list)


@dataclass
class StructuredMeasurement:
    line: str
    prefix: str | None
    label: str | None
    value: str | None
    unit: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _normalize_split_name(value: str | None) -> str:
    return _normalize_space(value or "").lower()


def _split_matches(record_split: str, requested_splits: set[str]) -> bool:
    if not requested_splits:
        return True
    return _normalize_split_name(record_split) in requested_splits


def _normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().replace(",", ".")


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = unit.strip()
    if not cleaned:
        return None
    aliases = {
        "mmhg": "mmHg",
        "m/s": "m/s",
        "cm/s": "cm/s",
        "m/s2": "m/s2",
        "cm": "cm",
        "mm": "mm",
        "ms": "ms",
        "s": "s",
        "%": "%",
        "ml": "ml",
        "cm2": "cm2",
        "ml/m2": "ml/m2",
        "bpm": "bpm",
    }
    return aliases.get(cleaned.lower(), cleaned)


def _canonicalize_line(text: str) -> str:
    line = _normalize_space(text)
    line = line.replace(r"\,", " ")
    line = line.replace(r"\%", " %")
    line = re.sub(r"\\text\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\s+([%])", r" \1", line)
    line = re.sub(r"(\d)(%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)\b", r"\1 \2", line)
    return _normalize_space(line)


def _parse_structured_measurement(text: str) -> StructuredMeasurement:
    line = _canonicalize_line(text)
    match = _LINE_PARSE_RE.match(line)
    if match is None:
        return StructuredMeasurement(line=line, prefix=None, label=line or None, value=None, unit=None)

    prefix = match.group("prefix")
    label = _normalize_space(match.group("label") or "") or None
    value = _normalize_value(match.group("value"))
    unit = _normalize_unit(match.group("unit"))

    return StructuredMeasurement(
        line=line,
        prefix=prefix,
        label=label,
        value=value,
        unit=unit,
    )


def _values_match(predicted: str | None, expected: str | None, tolerance: float = 0.011) -> bool:
    if predicted is None or expected is None:
        return predicted == expected
    try:
        return abs(float(predicted) - float(expected)) <= tolerance
    except Exception:
        return predicted.strip() == expected.strip()


def _string_equal(a: str | None, b: str | None) -> bool:
    return _normalize_space(a or "").lower() == _normalize_space(b or "").lower()


def _resolve_dataset_path(file_record: dict[str, Any], dataset_path: Path) -> Path:
    raw_path = str(file_record.get("file_path", "")).strip()
    if not raw_path:
        raise ValueError("Dataset entry is missing a non-empty 'file_path'.")
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _parse_requested_splits(raw: str) -> set[str]:
    return {
        _normalize_split_name(item)
        for item in raw.split(",")
        if _normalize_split_name(item)
    }


# ---------------------------------------------------------------------------
# JSON dataset loading
# ---------------------------------------------------------------------------


def parse_labels(labels_path: Path, *, split_filter: set[str] | None = None) -> list[LabeledFile]:
    """Load canonical JSON exact-line labels, optionally filtered by split."""
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Labels file must contain a top-level JSON object.")

    version = payload.get("version")
    if version != DATASET_VERSION:
        raise ValueError(
            f"Unsupported dataset version: {version!r} (expected {DATASET_VERSION})."
        )

    task = payload.get("task")
    if task != DATASET_TASK:
        raise ValueError(
            f"Unsupported dataset task: {task!r} (expected {DATASET_TASK!r})."
        )

    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("Labels file must contain a 'files' array.")

    requested_splits = split_filter or set()
    results: list[LabeledFile] = []

    for index, file_record in enumerate(files):
        if not isinstance(file_record, dict):
            raise ValueError(f"File record at index {index} must be an object.")

        file_name = str(file_record.get("file_name", "")).strip()
        file_path = _resolve_dataset_path(file_record, labels_path)
        if not file_name:
            file_name = file_path.name

        split = str(file_record.get("split", "")).strip()
        if not split:
            raise ValueError(f"File record {file_name!r} is missing required 'split'.")

        if not _split_matches(split, requested_splits):
            continue

        raw_measurements = file_record.get("measurements")
        if not isinstance(raw_measurements, list):
            raise ValueError(f"File record {file_name!r} must contain a 'measurements' array.")

        measurements: list[LabeledMeasurement] = []
        for measurement_index, measurement_record in enumerate(raw_measurements):
            if not isinstance(measurement_record, dict):
                raise ValueError(
                    f"Measurement record {measurement_index} for {file_name!r} must be an object."
                )
            text = str(measurement_record.get("text", "")).strip()
            if not text:
                continue
            order_raw = measurement_record.get("order")
            order = int(order_raw) if isinstance(order_raw, int) else None
            measurements.append(
                LabeledMeasurement(
                    text=_canonicalize_line(text),
                    order=order,
                )
            )

        results.append(
            LabeledFile(
                path=file_path,
                file_name=file_name,
                split=split,
                measurements=measurements,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    expected_text: str
    predicted_text: str | None
    expected_prefix: str | None
    predicted_prefix: str | None
    expected_label: str | None
    predicted_label: str | None
    expected_value: str | None
    predicted_value: str | None
    expected_unit: str | None
    predicted_unit: str | None
    line_match: bool
    prefix_match: bool
    label_match: bool
    value_match: bool
    unit_match: bool
    full_match: bool


@dataclass
class FrameDebugInfo:
    frame_index: int
    roi_bbox: tuple[int, int, int, int] | None
    ocr_bbox: tuple[int, int, int, int] | None
    roi_confidence: float
    raw_ocr_text: str
    predictions: list[dict[str, str | None]] = field(default_factory=list)


@dataclass
class FileEvaluationReport:
    file_path: str
    file_name: str
    split: str
    frames: list[FrameDebugInfo] = field(default_factory=list)
    labels: list[dict[str, str | None]] = field(default_factory=list)
    matches: list[MatchResult] = field(default_factory=list)
    total_labels: int = 0
    full_matches: int = 0
    line_matches: int = 0
    value_matches: int = 0
    label_matches: int = 0
    prefix_matches: int = 0
    predicted_count: int = 0
    elapsed_s: float = 0.0

    @property
    def full_match_rate(self) -> float:
        return self.full_matches / max(self.total_labels, 1)

    @property
    def line_match_rate(self) -> float:
        return self.line_matches / max(self.total_labels, 1)

    @property
    def value_match_rate(self) -> float:
        return self.value_matches / max(self.total_labels, 1)

    @property
    def label_match_rate(self) -> float:
        return self.label_matches / max(self.total_labels, 1)

    @property
    def prefix_match_rate(self) -> float:
        return self.prefix_matches / max(self.total_labels, 1)


def _prediction_to_structured_prediction(prediction: dict[str, str | None]) -> StructuredMeasurement:
    parts = [
        str(prediction.get("name") or "").strip(),
        str(prediction.get("value") or "").strip(),
        str(prediction.get("unit") or "").strip(),
    ]
    line = _canonicalize_line(" ".join(part for part in parts if part))
    return _parse_structured_measurement(line)


def score_predictions(
    labels: list[LabeledMeasurement],
    predictions: list[dict[str, str | None]],
) -> list[MatchResult]:
    """Score parser predictions against exact-line labels."""
    expected_items = [_parse_structured_measurement(item.text) for item in labels]
    predicted_items = [_prediction_to_structured_prediction(item) for item in predictions]
    used_preds: set[int] = set()
    results: list[MatchResult] = []

    for expected in expected_items:
        best_idx: int | None = None
        best_result: MatchResult | None = None
        best_score = -1

        for idx, predicted in enumerate(predicted_items):
            if idx in used_preds:
                continue

            line_match = _string_equal(predicted.line, expected.line)
            prefix_match = _string_equal(predicted.prefix, expected.prefix)
            label_match = _string_equal(predicted.label, expected.label)
            value_match = _values_match(predicted.value, expected.value)
            unit_match = _string_equal(predicted.unit, expected.unit)
            full_match = line_match

            score = 0
            if line_match:
                score += 100
            if prefix_match:
                score += 8
            if label_match:
                score += 4
            if value_match:
                score += 2
            if unit_match:
                score += 1

            candidate = MatchResult(
                expected_text=expected.line,
                predicted_text=predicted.line,
                expected_prefix=expected.prefix,
                predicted_prefix=predicted.prefix,
                expected_label=expected.label,
                predicted_label=predicted.label,
                expected_value=expected.value,
                predicted_value=predicted.value,
                expected_unit=expected.unit,
                predicted_unit=predicted.unit,
                line_match=line_match,
                prefix_match=prefix_match,
                label_match=label_match,
                value_match=value_match,
                unit_match=unit_match,
                full_match=full_match,
            )

            if score > best_score:
                best_score = score
                best_result = candidate
                best_idx = idx

            if full_match:
                break

        if best_result is not None and best_idx is not None:
            used_preds.add(best_idx)
            results.append(best_result)
        else:
            results.append(
                MatchResult(
                    expected_text=expected.line,
                    predicted_text=None,
                    expected_prefix=expected.prefix,
                    predicted_prefix=None,
                    expected_label=expected.label,
                    predicted_label=None,
                    expected_value=expected.value,
                    predicted_value=None,
                    expected_unit=expected.unit,
                    predicted_unit=None,
                    line_match=False,
                    prefix_match=False,
                    label_match=False,
                    value_match=False,
                    unit_match=False,
                    full_match=False,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def _build_frame_predictions(parser, raw_text: str) -> list[dict[str, str | None]]:
    measurements = parser.parse(raw_text, confidence=1.0)
    return [{"name": m.name, "value": m.value, "unit": m.unit} for m in measurements]


def run_evaluation(
    labels: list[LabeledFile],
    engine: OcrEngine,
    *,
    verbose: bool = True,
    args=None,
) -> dict[str, Any]:
    """Run the OCR pipeline on all labeled files using exact-line JSON labels."""
    detector = TopLeftBlueGrayBoxDetector()
    from app.pipeline.measurement_parsers import build_parser  # noqa: E402

    parser_name = getattr(args, "parser", "regex")
    parser = build_parser(parser_name)

    total_labels = 0
    total_full_match = 0
    total_line_match = 0
    total_value_match = 0
    total_label_match = 0
    total_prefix_match = 0
    total_detected = 0
    total_files = 0
    total_files_with_detections = 0
    elapsed_total = 0.0
    reports: list[FileEvaluationReport] = []

    for labeled_file in labels:
        if not labeled_file.path.exists():
            if verbose:
                print(f"  ⚠ SKIP (file not found): {labeled_file.file_name}")
            continue

        total_files += 1
        started = time.perf_counter()

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception as exc:
            if verbose:
                print(f"  ✗ LOAD ERROR: {labeled_file.file_name}: {exc}")
            total_labels += len(labeled_file.measurements)
            reports.append(
                FileEvaluationReport(
                    file_path=str(labeled_file.path),
                    file_name=labeled_file.file_name,
                    split=labeled_file.split,
                    labels=[
                        {
                            "text": item.text,
                            "order": str(item.order) if item.order is not None else None,
                        }
                        for item in labeled_file.measurements
                    ],
                    total_labels=len(labeled_file.measurements),
                )
            )
            continue

        all_predictions: list[dict[str, str | None]] = []
        frame_debug: list[FrameDebugInfo] = []

        for frame_idx in range(series.frame_count):
            frame = series.get_frame(frame_idx)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                frame_debug.append(
                    FrameDebugInfo(
                        frame_index=frame_idx,
                        roi_bbox=None,
                        ocr_bbox=None,
                        roi_confidence=detection.confidence,
                        raw_ocr_text="",
                        predictions=[],
                    )
                )
                continue

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            ocr_bbox = (x, y, bw, bh)
            if roi.shape[0] > HEADER_TRIM_PX:
                roi = roi[HEADER_TRIM_PX:, :]
                ocr_bbox = (x, y + HEADER_TRIM_PX, bw, bh - HEADER_TRIM_PX)

            prepared = preprocess_roi(roi)
            ocr_result = engine.extract(prepared)
            frame_predictions = _build_frame_predictions(parser, ocr_result.text)
            all_predictions.extend(frame_predictions)

            frame_debug.append(
                FrameDebugInfo(
                    frame_index=frame_idx,
                    roi_bbox=detection.bbox,
                    ocr_bbox=ocr_bbox,
                    roi_confidence=detection.confidence,
                    raw_ocr_text=ocr_result.text,
                    predictions=frame_predictions,
                )
            )

        elapsed = time.perf_counter() - started
        elapsed_total += elapsed

        if all_predictions:
            total_files_with_detections += 1

        match_results = score_predictions(labeled_file.measurements, all_predictions)
        n_labels = len(labeled_file.measurements)
        n_full = sum(1 for item in match_results if item.full_match)
        n_line = sum(1 for item in match_results if item.line_match)
        n_value = sum(1 for item in match_results if item.value_match)
        n_label = sum(1 for item in match_results if item.label_match)
        n_prefix = sum(1 for item in match_results if item.prefix_match)

        total_labels += n_labels
        total_full_match += n_full
        total_line_match += n_line
        total_value_match += n_value
        total_label_match += n_label
        total_prefix_match += n_prefix
        total_detected += len(all_predictions)

        report = FileEvaluationReport(
            file_path=str(labeled_file.path),
            file_name=labeled_file.file_name,
            split=labeled_file.split,
            frames=frame_debug,
            labels=[
                {
                    "text": item.text,
                    "order": str(item.order) if item.order is not None else None,
                }
                for item in labeled_file.measurements
            ],
            matches=match_results,
            total_labels=n_labels,
            full_matches=n_full,
            line_matches=n_line,
            value_matches=n_value,
            label_matches=n_label,
            prefix_matches=n_prefix,
            predicted_count=len(all_predictions),
            elapsed_s=elapsed,
        )
        reports.append(report)

        if verbose:
            status = "✓" if n_full == n_labels else "◐" if n_full > 0 else "✗"
            print(
                f"  {status} {labeled_file.file_name} [{labeled_file.split}]: "
                f"{n_full}/{n_labels} exact, "
                f"{n_value}/{n_labels} value, "
                f"{len(all_predictions)} preds, {elapsed:.1f}s"
            )
            print(f"    Expected lines ({len(labeled_file.measurements)}):")
            for item in labeled_file.measurements:
                print(f"      - {item.text}")

            print(f"    Predicted lines ({len(all_predictions)}):")
            if all_predictions:
                for pred in all_predictions:
                    structured = _prediction_to_structured_prediction(pred)
                    print(f"      - {structured.line}")
            else:
                print("      - NONE")

            print("    Frame ROI / OCR:")
            for frame_info in frame_debug:
                if frame_info.roi_bbox is None:
                    print(
                        f"      - frame={frame_info.frame_index}: ROI NOT DETECTED "
                        f"(conf={frame_info.roi_confidence:.3f})"
                    )
                    continue
                x, y, bw, bh = frame_info.roi_bbox
                cleaned = " ".join(frame_info.raw_ocr_text.split())
                ocr_bbox_str = ""
                if frame_info.ocr_bbox is not None:
                    ox, oy, ow, oh = frame_info.ocr_bbox
                    ocr_bbox_str = f" ocr_bbox=({ox},{oy},{ow},{oh})"
                print(
                    f"      - frame={frame_info.frame_index}: "
                    f"bbox=({x},{y},{bw},{bh}){ocr_bbox_str} conf={frame_info.roi_confidence:.3f}"
                )
                print(f"        OCR: {cleaned[:240] if cleaned else '<empty>'}")

            print("    Line-by-line results:")
            for result in match_results:
                predicted = result.predicted_text or "NOT FOUND"
                verdict = "OK" if result.full_match else "MISS"
                print(f"      - {verdict}: expected={result.expected_text} | predicted={predicted}")

    scores: dict[str, Any] = {
        "total_labels": float(total_labels),
        "total_full_match": float(total_full_match),
        "total_line_match": float(total_line_match),
        "total_value_match": float(total_value_match),
        "total_label_match": float(total_label_match),
        "total_prefix_match": float(total_prefix_match),
        "total_predicted": float(total_detected),
        "total_files": float(total_files),
        "total_files_with_detections": float(total_files_with_detections),
        "full_match_rate": total_full_match / max(total_labels, 1),
        "line_match_rate": total_line_match / max(total_labels, 1),
        "value_match_rate": total_value_match / max(total_labels, 1),
        "label_match_rate": total_label_match / max(total_labels, 1),
        "prefix_match_rate": total_prefix_match / max(total_labels, 1),
        "detection_rate": total_files_with_detections / max(total_files, 1),
        "elapsed_s": elapsed_total,
        "file_reports": reports,
        "file_details": [
            {
                "file_path": report.file_path,
                "file_name": report.file_name,
                "split": report.split,
                "frames": [
                    {
                        "frame_index": frame.frame_index,
                        "roi_bbox": list(frame.roi_bbox) if frame.roi_bbox is not None else None,
                        "ocr_bbox": list(frame.ocr_bbox) if frame.ocr_bbox is not None else None,
                        "roi_confidence": frame.roi_confidence,
                        "raw_ocr_text": frame.raw_ocr_text,
                        "predictions": frame.predictions,
                    }
                    for frame in report.frames
                ],
                "labels": report.labels,
                "matches": [
                    {
                        "expected_text": match.expected_text,
                        "predicted_text": match.predicted_text,
                        "expected_prefix": match.expected_prefix,
                        "predicted_prefix": match.predicted_prefix,
                        "expected_label": match.expected_label,
                        "predicted_label": match.predicted_label,
                        "expected_value": match.expected_value,
                        "predicted_value": match.predicted_value,
                        "expected_unit": match.expected_unit,
                        "predicted_unit": match.predicted_unit,
                        "line_match": match.line_match,
                        "prefix_match": match.prefix_match,
                        "label_match": match.label_match,
                        "value_match": match.value_match,
                        "unit_match": match.unit_match,
                        "full_match": match.full_match,
                    }
                    for match in report.matches
                ],
                "total_labels": report.total_labels,
                "full_matches": report.full_matches,
                "line_matches": report.line_matches,
                "value_matches": report.value_matches,
                "label_matches": report.label_matches,
                "prefix_matches": report.prefix_matches,
                "predicted_count": report.predicted_count,
                "elapsed_s": report.elapsed_s,
                "full_match_rate": report.full_match_rate,
                "line_match_rate": report.line_match_rate,
                "value_match_rate": report.value_match_rate,
                "label_match_rate": report.label_match_rate,
                "prefix_match_rate": report.prefix_match_rate,
            }
            for report in reports
        ],
    }
    return scores


def _print_summary(engine_name: str, scores: dict[str, float]) -> None:
    total = int(scores["total_labels"])
    full = int(scores["total_full_match"])
    line = int(scores["total_line_match"])
    value = int(scores["total_value_match"])
    label = int(scores["total_label_match"])
    prefix = int(scores["total_prefix_match"])
    preds = int(scores["total_predicted"])
    files = int(scores["total_files"])
    detected = int(scores["total_files_with_detections"])

    print(f"\n{'=' * 60}")
    print(f"  Engine: {engine_name}")
    print(f"  Files evaluated:       {files}")
    print(f"  Files with detections: {detected} ({scores['detection_rate']:.0%})")
    print(f"  Total labels:          {total}")
    print(f"  Total predictions:     {preds}")
    print(f"  Exact line matches:    {full}/{total} ({scores['full_match_rate']:.1%})")
    print(f"  Line matches:          {line}/{total} ({scores['line_match_rate']:.1%})")
    print(f"  Value matches:         {value}/{total} ({scores['value_match_rate']:.1%})")
    print(f"  Label matches:         {label}/{total} ({scores['label_match_rate']:.1%})")
    print(f"  Prefix matches:        {prefix}/{total} ({scores['prefix_match_rate']:.1%})")
    print(f"  Elapsed time:          {scores['elapsed_s']:.1f}s")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate echo OCR pipeline against exact-line JSON labels")
    parser.add_argument(
        "--engine",
        default="easyocr",
        help="OCR engine to use (tesseract, easyocr, paddleocr, surya)",
    )
    parser.add_argument(
        "--all-engines",
        action="store_true",
        help="Run evaluation with all available engines",
    )
    parser.add_argument(
        "--labels",
        default=str(DEFAULT_LABELS_PATH),
        help="Path to canonical JSON exact-line labels",
    )
    parser.add_argument(
        "--split",
        default="",
        help="Optional comma separated split filter (e.g. train,validation)",
    )
    parser.add_argument(
        "--parser",
        default="regex",
        help="Parser mode (regex, local_llm, hybrid)",
    )
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        print(f"Labels file not found: {labels_path}")
        sys.exit(1)

    requested_splits = _parse_requested_splits(args.split)
    labeled_files = parse_labels(labels_path, split_filter=requested_splits)
    if requested_splits:
        split_label = ", ".join(sorted(requested_splits))
        print(f"Using split filter: {split_label}")
    print(
        f"Parsed {len(labeled_files)} labeled files with "
        f"{sum(len(f.measurements) for f in labeled_files)} total measurement lines\n"
    )

    engines_to_test: list[str]
    if args.all_engines:
        engines_to_test = ["easyocr", "tesseract", "paddleocr", "surya"]
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
