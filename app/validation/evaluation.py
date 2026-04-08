from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.io.dicom_loader import load_dicom_series
from app.ocr.preprocessing import preprocess_roi
from app.pipeline.layout.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.measurements.line_first_parser import LineFirstParser
from app.pipeline.ocr.ocr_engines import OcrEngine
from app.validation.datasets import LabeledFile, LabeledMeasurement, canonicalize_label_line, normalize_space


HEADER_TRIM_PX = 0
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


@dataclass
class StructuredMeasurement:
    line: str
    prefix: str | None
    label: str | None
    value: str | None
    unit: str | None


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


def _parse_structured_measurement(text: str) -> StructuredMeasurement:
    line = canonicalize_label_line(text)
    match = _LINE_PARSE_RE.match(line)
    if match is None:
        return StructuredMeasurement(line=line, prefix=None, label=line or None, value=None, unit=None)

    prefix = match.group("prefix")
    label = normalize_space(match.group("label") or "") or None
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
    return normalize_space(a or "").lower() == normalize_space(b or "").lower()


def _prediction_to_structured_prediction(prediction: dict[str, str | None]) -> StructuredMeasurement:
    parts = [
        str(prediction.get("name") or "").strip(),
        str(prediction.get("value") or "").strip(),
        str(prediction.get("unit") or "").strip(),
    ]
    line = canonicalize_label_line(" ".join(part for part in parts if part))
    return _parse_structured_measurement(line)


def score_predictions(
    labels: list[LabeledMeasurement],
    predictions: list[dict[str, str | None]],
) -> list[MatchResult]:
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
            # Only score component matches when the expected side actually contains that component.
            # This avoids rewarding unrelated predictions just because both sides have missing fields.
            if expected.prefix is not None and prefix_match:
                score += 8
            if expected.label is not None and label_match:
                score += 16
            if expected.value is not None and value_match:
                score += 12
            if expected.unit is not None and unit_match:
                score += 6

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

        plausible_match = (
            best_result is not None
            and (
                best_result.line_match
                or best_result.label_match
                or (best_result.value_match and expected.value is not None)
            )
        )

        if best_result is not None and best_idx is not None and plausible_match:
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


def _build_frame_predictions(raw_text: str) -> list[dict[str, str | None]]:
    measurements = LineFirstParser().parse(raw_text, confidence=1.0)
    return [{"name": m.name, "value": m.value, "unit": m.unit} for m in measurements]


def run_evaluation(
    labels: list[LabeledFile],
    engine: OcrEngine,
    *,
    verbose: bool = True,
    args: Any = None,
) -> dict[str, Any]:
    detector = TopLeftBlueGrayBoxDetector()
    _ = args

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
                print(f"  SKIP (file not found): {labeled_file.file_name}")
            continue

        total_files += 1
        started = time.perf_counter()

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception as exc:
            if verbose:
                print(f"  LOAD ERROR: {labeled_file.file_name}: {exc}")
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
            if HEADER_TRIM_PX > 0 and roi.shape[0] > HEADER_TRIM_PX:
                roi = roi[HEADER_TRIM_PX:, :]
                ocr_bbox = (x, y + HEADER_TRIM_PX, bw, bh - HEADER_TRIM_PX)

            prepared = preprocess_roi(roi)
            ocr_result = engine.extract(prepared)
            frame_predictions = _build_frame_predictions(ocr_result.text)
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

        # Count label files where TopLeftBlueGrayBoxDetector found a panel ROI on at least one
        # frame (so OCR ran and produced predictions). Not related to discovering files on disk.
        if all_predictions:
            total_files_with_detections += 1

        match_results = score_predictions(labeled_file.measurements, all_predictions)
        label_count = len(labeled_file.measurements)
        full_count = sum(1 for item in match_results if item.full_match)
        line_count = sum(1 for item in match_results if item.line_match)
        value_count = sum(1 for item in match_results if item.value_match)
        match_label_count = sum(1 for item in match_results if item.label_match)
        prefix_count = sum(1 for item in match_results if item.prefix_match)

        total_labels += label_count
        total_full_match += full_count
        total_line_match += line_count
        total_value_match += value_count
        total_label_match += match_label_count
        total_prefix_match += prefix_count
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
            total_labels=label_count,
            full_matches=full_count,
            line_matches=line_count,
            value_matches=value_count,
            label_matches=match_label_count,
            prefix_matches=prefix_count,
            predicted_count=len(all_predictions),
            elapsed_s=elapsed,
        )
        reports.append(report)

        if verbose:
            status = "OK" if full_count == label_count else "PARTIAL" if full_count > 0 else "MISS"
            print(
                f"  {status} {labeled_file.file_name} [{labeled_file.split}]: "
                f"{full_count}/{label_count} exact, "
                f"{value_count}/{label_count} value, "
                f"{len(all_predictions)} preds, {elapsed:.1f}s"
            )
            print(f"    Expected lines ({len(labeled_file.measurements)}):")
            for item in labeled_file.measurements:
                print(f"      - {item.text}")

            print(f"    Predicted lines ({len(all_predictions)}):")
            if all_predictions:
                for prediction in all_predictions:
                    structured = _prediction_to_structured_prediction(prediction)
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

    return {
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


def print_summary(engine_name: str, scores: dict[str, float]) -> None:
    total = int(scores["total_labels"])
    full = int(scores["total_full_match"])
    line = int(scores["total_line_match"])
    value = int(scores["total_value_match"])
    label = int(scores["total_label_match"])
    prefix = int(scores["total_prefix_match"])
    predictions = int(scores["total_predicted"])
    files = int(scores["total_files"])
    detected = int(scores["total_files_with_detections"])

    print(f"\n{'=' * 60}")
    print(f"  Engine: {engine_name}")
    print(f"  Label files evaluated:              {files}")
    print(
        f"  Files with panel ROI (≥1 frame):    {detected}/{files} "
        f"({scores['detection_rate']:.0%})  [TopLeftBlueGrayBoxDetector]"
    )
    print(f"  Total labels:          {total}")
    print(f"  Total predictions:     {predictions}")
    print(f"  Exact line matches:    {full}/{total} ({scores['full_match_rate']:.1%})")
    print(f"  Line matches:          {line}/{total} ({scores['line_match_rate']:.1%})")
    print(f"  Value matches:         {value}/{total} ({scores['value_match_rate']:.1%})")
    print(f"  Label matches:         {label}/{total} ({scores['label_match_rate']:.1%})")
    print(f"  Prefix matches:        {prefix}/{total} ({scores['prefix_match_rate']:.1%})")
    print(f"  Elapsed time:          {scores['elapsed_s']:.1f}s")
    print(f"{'=' * 60}")
