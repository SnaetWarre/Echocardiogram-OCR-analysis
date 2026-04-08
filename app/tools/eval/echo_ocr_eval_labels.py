"""Evaluate the echo-OCR pipeline against a canonical JSON exact-line dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.ocr.preprocessing import preprocess_roi  # noqa: E402
from app.pipeline.layout.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.pipeline.echo_ocr_pipeline import DEFAULT_OCR_ENGINE  # noqa: E402
from app.pipeline.ocr.ocr_engines import build_engine  # noqa: E402
from app.validation.datasets import (  # noqa: E402
    DATASET_TASK,
    DATASET_VERSION,
    DEFAULT_LABELS_PATH,
    LabeledFile,
    LabeledMeasurement,
    parse_labels,
    parse_requested_splits,
)
from app.validation.evaluation import (  # noqa: E402
    HEADER_TRIM_PX,
    StructuredMeasurement,
    print_summary,
    run_evaluation,
    score_predictions,
)

_print_summary = print_summary

__all__ = [
    "DATASET_TASK",
    "DATASET_VERSION",
    "DEFAULT_LABELS_PATH",
    "HEADER_TRIM_PX",
    "LabeledFile",
    "LabeledMeasurement",
    "StructuredMeasurement",
    "TopLeftBlueGrayBoxDetector",
    "_print_summary",
    "parse_labels",
    "parse_requested_splits",
    "preprocess_roi",
    "print_summary",
    "run_evaluation",
    "score_predictions",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate echo OCR pipeline against exact-line JSON labels"
    )
    parser.add_argument(
        "--engine",
        default=DEFAULT_OCR_ENGINE,
        help="OCR engine to use (glm-ocr, surya, tesseract, easyocr, paddleocr)",
    )
    parser.add_argument(
        "--all-engines",
        action="store_true",
        help="Run evaluation with all available engines",
    )
    parser.add_argument(
        "--labels",
        default=str(DEFAULT_LABELS_PATH),
        help="Path to the canonical JSON labels file",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Optional split filter (comma separated, e.g. train,validation)",
    )
    parser.add_argument(
        "--parser",
        default="",
        help="Ignored; evaluation uses line-first measurement decoding.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path to write the full evaluation payload as JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file OCR dump (still prints summary and json-out path)",
    )
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise SystemExit(f"Labels file not found: {labels_path}")

    requested_splits = parse_requested_splits(args.split)
    labeled_files = parse_labels(labels_path, split_filter=requested_splits)

    if requested_splits:
        print(f"Loaded split filter: {', '.join(sorted(requested_splits))}")
    print(f"Loaded {len(labeled_files)} labeled files")

    engine_names = (
        ["glm-ocr", "surya", "tesseract", "easyocr", "paddleocr"] if args.all_engines else [args.engine]
    )
    all_scores: dict[str, dict[str, Any]] = {}
    for engine_name in engine_names:
        print(f"\n--- Evaluating with: {engine_name} ---")
        engine = build_engine(engine_name)
        scores = run_evaluation(labeled_files, engine, verbose=not args.quiet, args=args)
        print_summary(engine_name, scores)
        all_scores[engine_name] = scores

    if args.json_out:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        serializable_payload = {
            engine_name: {
                key: value
                for key, value in engine_scores.items()
                if key != "file_reports"
            }
            for engine_name, engine_scores in all_scores.items()
        }
        output_path.write_text(
            json.dumps(serializable_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nSaved JSON evaluation payload to {output_path}")


if __name__ == "__main__":
    main()
