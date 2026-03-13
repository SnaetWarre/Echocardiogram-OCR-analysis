from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline  # noqa: E402
from app.pipeline.ai_pipeline import PipelineConfig  # noqa: E402
from app.pipeline.measurement_decoder import parse_measurement_line  # noqa: E402
from app.tools.echo_ocr_eval_labels import (  # noqa: E402
    DEFAULT_LABELS_PATH,
    LabeledFile,
    parse_labels,
)


def _empty_file_reports() -> list[dict[str, Any]]:
    return []


@dataclass
class LineMetricTotals:
    total_files: int = 0
    total_labels: int = 0
    exact_line_matches: int = 0
    label_matches: int = 0
    value_matches: int = 0
    unit_matches: int = 0
    prefix_matches: int = 0
    uncertainty_count: int = 0
    fallback_invocations: int = 0
    engine_disagreements: int = 0
    roi_detection_failures: int = 0
    line_segmentation_failures: int = 0
    ocr_predictions: int = 0
    file_reports: list[dict[str, Any]] = field(default_factory=_empty_file_reports)


def _match_count(predicted_lines: list[str], expected_lines: list[str]) -> dict[str, int]:
    remaining = list(predicted_lines)
    exact = label = value = unit = prefix = 0
    for expected in expected_lines:
        expected_decoded = parse_measurement_line(expected)
        best_index = None
        best_score = -1
        best_decoded = None
        for idx, predicted in enumerate(remaining):
            predicted_decoded = parse_measurement_line(predicted)
            score = 0
            if predicted_decoded.canonical_text == expected_decoded.canonical_text:
                score += 100
            if predicted_decoded.label == expected_decoded.label:
                score += 10
            if predicted_decoded.value == expected_decoded.value:
                score += 5
            if predicted_decoded.unit == expected_decoded.unit:
                score += 2
            if predicted_decoded.prefix == expected_decoded.prefix:
                score += 1
            if score > best_score:
                best_score = score
                best_index = idx
                best_decoded = predicted_decoded
        if best_index is None or best_decoded is None:
            continue
        matched = remaining.pop(best_index)
        matched_decoded = parse_measurement_line(matched)
        if matched_decoded.canonical_text == expected_decoded.canonical_text:
            exact += 1
        if matched_decoded.label == expected_decoded.label:
            label += 1
        if matched_decoded.value == expected_decoded.value:
            value += 1
        if matched_decoded.unit == expected_decoded.unit:
            unit += 1
        if matched_decoded.prefix == expected_decoded.prefix:
            prefix += 1
    return {
        "exact": exact,
        "label": label,
        "value": value,
        "unit": unit,
        "prefix": prefix,
    }


def evaluate_line_transcription(
    labels: list[LabeledFile],
    *,
    engine_name: str,
    fallback_engine_name: str = "",
    max_files: int | None = None,
) -> LineMetricTotals:
    totals = LineMetricTotals()
    pipeline = EchoOcrPipeline(
        config=PipelineConfig(
            parameters={
                "ocr_engine": engine_name,
                "fallback_ocr_engine": fallback_engine_name,
                "parser_mode": "regex",
                "max_frames": 1,
            }
        ),
    )
    pipeline.ensure_components()

    selected_labels = labels[: max_files or len(labels)]
    totals.total_files = len(selected_labels)

    for labeled_file in selected_labels:
        if not labeled_file.path.exists():
            continue
        from app.io.dicom_loader import load_dicom_series

        series = load_dicom_series(labeled_file.path, load_pixels=True)
        expected_lines = [item.text for item in labeled_file.measurements]
        totals.total_labels += len(expected_lines)

        file_predicted_lines: list[str] = []
        file_uncertainty_count = 0
        file_fallback_invocations = 0
        file_engine_disagreements = 0
        roi_detected = False

        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            detection = pipeline.box_detector.detect(frame)
            if not detection.present or detection.bbox is None:
                continue
            roi_detected = True
            ocr, panel, _measurements, _bbox = pipeline.analyze_frame(frame)
            if ocr is None:
                continue
            if not panel.lines:
                totals.line_segmentation_failures += 1
                continue
            file_predicted_lines.extend(line.text for line in panel.lines if line.text)
            file_uncertainty_count += panel.uncertain_line_count
            file_fallback_invocations += panel.fallback_invocations
            file_engine_disagreements += panel.engine_disagreement_count

        if not roi_detected:
            totals.roi_detection_failures += 1

        totals.ocr_predictions += len(file_predicted_lines)
        totals.uncertainty_count += file_uncertainty_count
        totals.fallback_invocations += file_fallback_invocations
        totals.engine_disagreements += file_engine_disagreements

        matches = _match_count(file_predicted_lines, expected_lines)
        totals.exact_line_matches += matches["exact"]
        totals.label_matches += matches["label"]
        totals.value_matches += matches["value"]
        totals.unit_matches += matches["unit"]
        totals.prefix_matches += matches["prefix"]
        totals.file_reports.append(
            {
                "file_name": labeled_file.file_name,
                "file_path": str(labeled_file.path),
                "split": labeled_file.split,
                "expected_lines": expected_lines,
                "predicted_lines": file_predicted_lines,
                "uncertainty_count": file_uncertainty_count,
                "fallback_invocations": file_fallback_invocations,
                "engine_disagreements": file_engine_disagreements,
                **matches,
            }
        )

    return totals


def _rates(totals: LineMetricTotals) -> dict[str, float]:
    denominator = max(totals.total_labels, 1)
    file_denominator = max(totals.total_files, 1)
    return {
        "exact_line_match_rate": totals.exact_line_matches / denominator,
        "label_match_rate": totals.label_matches / denominator,
        "value_match_rate": totals.value_matches / denominator,
        "unit_match_rate": totals.unit_matches / denominator,
        "prefix_match_rate": totals.prefix_matches / denominator,
        "uncertainty_rate": totals.uncertainty_count / max(totals.ocr_predictions, 1),
        "fallback_invocation_rate": totals.fallback_invocations / max(totals.ocr_predictions, 1),
        "roi_detection_failure_rate": totals.roi_detection_failures / file_denominator,
        "line_segmentation_failure_rate": totals.line_segmentation_failures / max(totals.ocr_predictions, 1),
        "engine_disagreement_rate": totals.engine_disagreements / max(totals.ocr_predictions, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate line-first OCR transcription metrics")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_PATH), help="Path to exact_lines.json")
    parser.add_argument("--split", default="validation", help="Optional comma separated split filter")
    parser.add_argument("--engine", default="easyocr", help="Primary OCR engine")
    parser.add_argument("--fallback-engine", default="", help="Fallback OCR engine")
    parser.add_argument("--max-files", type=int, default=0, help="Optional file limit for quick runs")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    split_filter = {item.strip().lower() for item in args.split.split(",") if item.strip()}
    labels = parse_labels(Path(args.labels), split_filter=split_filter)
    totals = evaluate_line_transcription(
        labels,
        engine_name=args.engine,
        fallback_engine_name=args.fallback_engine,
        max_files=args.max_files or None,
    )
    summary = {
        "total_files": totals.total_files,
        "total_labels": totals.total_labels,
        "ocr_predictions": totals.ocr_predictions,
        "exact_line_matches": totals.exact_line_matches,
        "label_matches": totals.label_matches,
        "value_matches": totals.value_matches,
        "unit_matches": totals.unit_matches,
        "prefix_matches": totals.prefix_matches,
        "uncertainty_count": totals.uncertainty_count,
        "fallback_invocations": totals.fallback_invocations,
        "engine_disagreements": totals.engine_disagreements,
        "roi_detection_failures": totals.roi_detection_failures,
        "line_segmentation_failures": totals.line_segmentation_failures,
        **_rates(totals),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({**summary, "file_reports": totals.file_reports}, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
