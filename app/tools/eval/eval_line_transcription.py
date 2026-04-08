from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from app.pipeline.echo_ocr_pipeline import (  # noqa: E402
    DEFAULT_OCR_ENGINE,
    DEFAULT_PARSER_MODE,
    DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX,
    EchoOcrPipeline,
)
from app.pipeline.ai_pipeline import PipelineConfig  # noqa: E402
from app.pipeline.layout.line_segmenter import SegmentationResult  # noqa: E402
from app.pipeline.measurements.measurement_decoder import parse_measurement_line  # noqa: E402
from app.validation.datasets import (  # noqa: E402
    DEFAULT_LABELS_PATH,
    LabeledFile,
    parse_labels,
)


def _empty_file_reports() -> list[dict[str, Any]]:
    return []


def _empty_hard_cases() -> list[dict[str, Any]]:
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
    vision_invocations: int = 0
    engine_disagreements: int = 0
    roi_detection_failures: int = 0
    line_segmentation_failures: int = 0
    ocr_predictions: int = 0
    file_reports: list[dict[str, Any]] = field(default_factory=_empty_file_reports)
    hard_cases: list[dict[str, Any]] = field(default_factory=_empty_hard_cases)


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


def _sequence_similarity(expected_lines: list[str], predicted_lines: list[str]) -> float:
    return SequenceMatcher(None, "\n".join(expected_lines), "\n".join(predicted_lines)).ratio()


def _save_segmentation_debug_image(
    *,
    pipeline: EchoOcrPipeline,
    frame: np.ndarray,
    segmentation: SegmentationResult,
    output_path: Path,
) -> str | None:
    try:
        pipeline.save_segmentation_debug_image(frame, segmentation, output_path)
    except Exception:
        return None
    return str(output_path)


def evaluate_line_transcription(
    labels: list[LabeledFile],
    *,
    engine_name: str,
    fallback_engine_name: str = "",
    pipeline_parameters: dict[str, object] | None = None,
    max_files: int | None = None,
    debug_dir: Path | None = None,
    hard_case_limit: int = 0,
) -> LineMetricTotals:
    totals = LineMetricTotals()
    parameters: dict[str, object] = {
        "ocr_engine": engine_name,
        "fallback_ocr_engine": fallback_engine_name,
        "parser_mode": DEFAULT_PARSER_MODE,
        "max_frames": 1,
        # Avoid silent chain to tesseract/easyocr/paddle when the requested fallback fails to load.
        "strict_ocr_engine_selection": True,
    }
    if pipeline_parameters:
        parameters.update(pipeline_parameters)
    pipeline = EchoOcrPipeline(
        config=PipelineConfig(
            parameters=parameters
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
        file_vision_invocations = 0
        file_engine_disagreements = 0
        roi_detected = False
        segmentation_line_count = 0
        saved_debug_images: list[str] = []

        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            detection = pipeline.box_detector.detect(frame)
            if not detection.present or detection.bbox is None:
                continue
            roi_detected = True
            detection, segmentation, _ocr, panel, _measurements, _bbox = pipeline.analyze_frame_with_debug(frame)
            if not panel.lines:
                totals.line_segmentation_failures += 1
                continue
            segmentation_line_count += len(segmentation.lines)
            file_predicted_lines.extend(line.text for line in panel.lines if line.text)
            file_uncertainty_count += panel.uncertain_line_count
            file_fallback_invocations += panel.fallback_invocations
            file_vision_invocations += int(getattr(panel, "vision_invocations", 0) or 0)
            file_engine_disagreements += panel.engine_disagreement_count

        if not roi_detected:
            totals.roi_detection_failures += 1

        totals.ocr_predictions += len(file_predicted_lines)
        totals.uncertainty_count += file_uncertainty_count
        totals.fallback_invocations += file_fallback_invocations
        totals.vision_invocations += file_vision_invocations
        totals.engine_disagreements += file_engine_disagreements

        matches = _match_count(file_predicted_lines, expected_lines)
        similarity = _sequence_similarity(expected_lines, file_predicted_lines)
        totals.exact_line_matches += matches["exact"]
        totals.label_matches += matches["label"]
        totals.value_matches += matches["value"]
        totals.unit_matches += matches["unit"]
        totals.prefix_matches += matches["prefix"]
        file_report = {
            "file_name": labeled_file.file_name,
            "file_path": str(labeled_file.path),
            "split": labeled_file.split,
            "expected_lines": expected_lines,
            "predicted_lines": file_predicted_lines,
            "uncertainty_count": file_uncertainty_count,
            "fallback_invocations": file_fallback_invocations,
            "vision_invocations": file_vision_invocations,
            "engine_disagreements": file_engine_disagreements,
            "segmentation_line_count": segmentation_line_count,
            "sequence_similarity": similarity,
            "debug_images": saved_debug_images,
            **matches,
        }
        totals.file_reports.append(file_report)

        is_hard_case = matches["exact"] < len(expected_lines) or len(file_predicted_lines) != len(expected_lines)
        if is_hard_case and debug_dir is not None and (hard_case_limit <= 0 or len(totals.hard_cases) < hard_case_limit):
            try:
                frame = series.get_frame(0)
                detection, segmentation, _ocr, _panel, _measurements, _bbox = pipeline.analyze_frame_with_debug(frame)
                if detection.present and detection.bbox is not None:
                    x, y, bw, bh = detection.bbox
                    roi = frame[y : y + bh, x : x + bw]
                    debug_path = debug_dir / f"{labeled_file.file_name}__frame_000_segmentation.png"
                    saved_path = _save_segmentation_debug_image(
                        pipeline=pipeline,
                        frame=roi,
                        segmentation=segmentation,
                        output_path=debug_path,
                    )
                    if saved_path:
                        saved_debug_images.append(saved_path)
                        file_report["debug_images"] = saved_debug_images
            except Exception:
                pass
            totals.hard_cases.append(file_report)

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
        "vision_invocation_rate": totals.vision_invocations / max(totals.ocr_predictions, 1),
        "roi_detection_failure_rate": totals.roi_detection_failures / file_denominator,
        "line_segmentation_failure_rate": totals.line_segmentation_failures / max(totals.ocr_predictions, 1),
        "engine_disagreement_rate": totals.engine_disagreements / max(totals.ocr_predictions, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate line-first OCR transcription metrics")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_PATH), help="Path to exact_lines.json")
    parser.add_argument("--split", default="validation", help="Optional comma separated split filter")
    parser.add_argument("--engine", default=DEFAULT_OCR_ENGINE, help="Primary OCR engine")
    parser.add_argument(
        "--fallback-engine",
        default="",
        help="Optional per-line fallback (e.g. surya). Default empty = primary engine only (no tesseract chain).",
    )
    parser.add_argument("--max-files", type=int, default=0, help="Optional file limit for quick runs")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    parser.add_argument("--debug-dir", default="", help="Optional directory for segmentation debug images")
    parser.add_argument("--hard-case-limit", type=int, default=0, help="Optional maximum number of hard-case debug exports; 0 means no limit")
    parser.add_argument("--parser-mode", default=DEFAULT_PARSER_MODE, help="Pipeline parser mode")
    parser.add_argument("--llm-model", default="qwen2.5:7b-instruct-q4_K_M", help="Local text model for parser/panel validation")
    parser.add_argument("--llm-command", default="ollama", help="Local text model command")
    parser.add_argument("--panel-validation-mode", default="off", help="Panel validation mode (off, selective, always)")
    parser.add_argument("--vision-fallback", action="store_true", help="Enable selective local vision fallback")
    parser.add_argument("--vision-model", default="qwen2.5vl:3b-q4_K_M", help="Local vision model for hard lines")
    parser.add_argument("--vision-ollama-url", default="http://127.0.0.1:11434", help="Ollama base URL for vision fallback")
    parser.add_argument("--study-companion", action="store_true", help="Enable study companion discovery during evaluation")
    parser.add_argument(
        "--segmentation-extra-left-pad",
        type=int,
        default=DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX,
        help="Widen line crops left (segmentation_extra_left_pad_px); 0 disables extra margin",
    )
    args = parser.parse_args()

    split_filter = {item.strip().lower() for item in args.split.split(",") if item.strip()}
    labels = parse_labels(Path(args.labels), split_filter=split_filter)
    totals = evaluate_line_transcription(
        labels,
        engine_name=args.engine,
        fallback_engine_name=args.fallback_engine,
        pipeline_parameters={
            "parser_mode": args.parser_mode,
            "llm_model": args.llm_model,
            "llm_command": args.llm_command,
            "panel_validation_mode": args.panel_validation_mode,
            "panel_validation_model": args.llm_model,
            "panel_validation_command": args.llm_command,
            "vision_fallback_enabled": args.vision_fallback,
            "vision_model": args.vision_model,
            "vision_ollama_url": args.vision_ollama_url,
            "study_companion_enabled": args.study_companion,
            "segmentation_extra_left_pad_px": max(0, int(args.segmentation_extra_left_pad)),
        },
        max_files=args.max_files or None,
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        hard_case_limit=args.hard_case_limit,
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
        "vision_invocations": totals.vision_invocations,
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
            json.dumps({**summary, "file_reports": totals.file_reports, "hard_cases": totals.hard_cases}, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
