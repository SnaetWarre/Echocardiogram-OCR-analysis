"""Evaluate line segmentation + OCR against exact_lines.json ground truth.

Usage (from project root):
    mamba run -n DL python -m app.tools.eval_segmentation

Runs each labelled file through row-projection segmentation with optional ROI
smoothing on the line crops, and prints per-file + aggregate accuracy.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.ocr.preprocessing import preprocess_roi
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.line_segmenter import LineSegmenter
from app.pipeline.line_transcriber import LineTranscriber
from app.pipeline.measurement_decoder import canonicalize_exact_line
from app.pipeline.ocr_engines import build_engine


LABELS_PATH = Path("labels/exact_lines.json")


def _normalize(text: str) -> str:
    return canonicalize_exact_line(text).strip().lower()


def _run_pipeline_on_file(
    file_path: Path,
    engine: Any,
    segmenter: LineSegmenter,
    transcriber: LineTranscriber,
) -> list[str]:
    series = load_dicom_series(file_path, load_pixels=False)
    frame = series.get_frame(0)
    det = TopLeftBlueGrayBoxDetector().detect(frame)
    if not det.present or det.bbox is None:
        return []
    x, y, bw, bh = det.bbox
    roi = frame[y : y + bh, x : x + bw]
    scout = engine.extract(roi)
    seg = segmenter.segment(roi, tokens=scout.tokens)
    panel = transcriber.transcribe(
        roi,
        seg,
        primary_engine=engine,
        fallback_engine=None,
        vision_expert=None,
    )
    return [line.text for line in panel.lines if line.text.strip()]


def _score(predicted: list[str], expected: list[str]) -> dict[str, Any]:
    norm_pred = [_normalize(text) for text in predicted]
    norm_exp = [_normalize(text) for text in expected]
    exact_matches = sum(1 for predicted_line, expected_line in zip(norm_pred, norm_exp) if predicted_line == expected_line)
    total = len(norm_exp)
    return {
        "predicted": predicted,
        "expected": expected,
        "exact_matches": exact_matches,
        "total": total,
        "accuracy": exact_matches / total if total else 1.0,
    }


def main() -> None:
    with LABELS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)

    engine = build_engine("surya")
    configs: dict[str, dict[str, Any]] = {
        "baseline": {"smooth": False},
        "smooth only": {"smooth": True},
    }

    all_results: dict[str, list[dict[str, Any]]] = {name: [] for name in configs}
    files = data["files"]
    for file_idx, entry in enumerate(files):
        file_path = Path(entry["file_path"])
        expected = [measurement["text"] for measurement in entry["measurements"]]
        file_name = entry["file_name"]

        if not file_path.exists():
            print(f"  [{file_idx + 1}/{len(files)}] SKIP {file_name} (file not found)")
            continue

        print(
            f"  [{file_idx + 1}/{len(files)}] {file_name} ({len(expected)} lines) ... ",
            end="",
            flush=True,
        )

        for config_name, cfg in configs.items():
            segmenter = LineSegmenter(
                segmentation_mode="row_projection",
                target_line_height_px=20.0,
            )

            def _preprocess(image: np.ndarray, _smooth: bool = cfg["smooth"]) -> np.ndarray:
                return preprocess_roi(
                    image,
                    scale_factor=3,
                    scale_algo="lanczos",
                    contrast_mode="none",
                    smooth=_smooth,
                )

            transcriber = LineTranscriber(preprocess_views={"default": _preprocess})
            started = time.time()
            predicted = _run_pipeline_on_file(file_path, engine, segmenter, transcriber)
            elapsed = time.time() - started

            score = _score(predicted, expected)
            score["elapsed_s"] = round(elapsed, 2)
            score["file_name"] = file_name
            all_results[config_name].append(score)

        acc_str = "  ".join(
            f"{name}: {all_results[name][-1]['accuracy']:.0%}"
            for name in configs
        )
        print(acc_str)

        last = all_results[list(configs.keys())[0]][-1]
        if last["accuracy"] < 1.0:
            for name in configs:
                result = all_results[name][-1]
                if result["accuracy"] < 1.0:
                    print(f"    [{name}] predicted: {result['predicted']}")
            print(f"    expected:  {last['expected']}")

    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    for config_name in configs:
        results = all_results[config_name]
        if not results:
            continue
        total_exact = sum(result["exact_matches"] for result in results)
        total_lines = sum(result["total"] for result in results)
        total_time = sum(result["elapsed_s"] for result in results)
        perfect_files = sum(1 for result in results if result["accuracy"] == 1.0)
        accuracy = total_exact / total_lines if total_lines else 0.0
        print(
            f"  {config_name:30s}  "
            f"lines={total_exact}/{total_lines} ({accuracy:.1%})  "
            f"perfect_files={perfect_files}/{len(results)}  "
            f"time={total_time:.1f}s"
        )


if __name__ == "__main__":
    main()
