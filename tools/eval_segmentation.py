"""Evaluate line segmentation + OCR against exact_lines.json ground truth.

Usage (from project root):
    mamba run -n DL python tools/eval_segmentation.py

Runs each labelled file through the pipeline with both the old (even-split)
and new (valley-snapped) fixed_pitch segmentation, optionally with smoothing,
and prints per-file + aggregate accuracy.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.io.dicom_loader import load_dicom_series
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.echo_ocr_pipeline import preprocess_roi
from app.pipeline.line_segmenter import LineSegmenter
from app.pipeline.line_transcriber import LineTranscriber, PanelTranscription
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
    norm_pred = [_normalize(t) for t in predicted]
    norm_exp = [_normalize(t) for t in expected]
    exact_matches = sum(1 for p, e in zip(norm_pred, norm_exp) if p == e)
    total = len(norm_exp)
    return {
        "predicted": predicted,
        "expected": expected,
        "exact_matches": exact_matches,
        "total": total,
        "accuracy": exact_matches / total if total else 1.0,
    }


def main() -> None:
    with open(LABELS_PATH) as f:
        data = json.load(f)

    engine = build_engine("surya")
    detector = TopLeftBlueGrayBoxDetector()

    configs: dict[str, dict[str, Any]] = {
        "baseline": {"snap_to_valleys": False, "smooth": False},
        "smooth only": {"snap_to_valleys": False, "smooth": True},
        "valley-snap only": {"snap_to_valleys": True, "smooth": False},
        "valley-snap + smooth": {"snap_to_valleys": True, "smooth": True},
    }

    all_results: dict[str, list[dict[str, Any]]] = {name: [] for name in configs}

    files = data["files"]
    for file_idx, entry in enumerate(files):
        file_path = Path(entry["file_path"])
        expected = [m["text"] for m in entry["measurements"]]
        file_name = entry["file_name"]

        if not file_path.exists():
            print(f"  [{file_idx+1}/{len(files)}] SKIP {file_name} (file not found)")
            continue

        print(f"  [{file_idx+1}/{len(files)}] {file_name} ({len(expected)} lines) ... ", end="", flush=True)

        for config_name, cfg in configs.items():
            segmenter = LineSegmenter(
                segmentation_mode="fixed_pitch",
                target_line_height_px=20.0,
                snap_to_valleys=cfg["snap_to_valleys"],
            )

            def _preprocess(image: np.ndarray, _smooth: bool = cfg["smooth"]) -> np.ndarray:
                return preprocess_roi(image, scale_factor=3, scale_algo="lanczos", contrast_mode="none", smooth=_smooth)

            transcriber = LineTranscriber(
                preprocess_views={"default": _preprocess},
            )

            t0 = time.time()
            predicted = _run_pipeline_on_file(file_path, engine, segmenter, transcriber)
            elapsed = time.time() - t0

            score = _score(predicted, expected)
            score["elapsed_s"] = round(elapsed, 2)
            score["file_name"] = file_name
            all_results[config_name].append(score)

        best_cfg = max(configs.keys(), key=lambda k: all_results[k][-1]["accuracy"])
        acc_str = "  ".join(
            f"{name}: {all_results[name][-1]['accuracy']:.0%}"
            for name in configs
        )
        print(f"{acc_str}")

        last = all_results[list(configs.keys())[0]][-1]
        if last["accuracy"] < 1.0:
            for name in configs:
                r = all_results[name][-1]
                if r["accuracy"] < 1.0:
                    print(f"    [{name}] predicted: {r['predicted']}")
            print(f"    expected:  {last['expected']}")

    print("\n" + "=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    for config_name in configs:
        results = all_results[config_name]
        if not results:
            continue
        total_exact = sum(r["exact_matches"] for r in results)
        total_lines = sum(r["total"] for r in results)
        total_time = sum(r["elapsed_s"] for r in results)
        perfect_files = sum(1 for r in results if r["accuracy"] == 1.0)
        accuracy = total_exact / total_lines if total_lines else 0.0
        print(
            f"  {config_name:30s}  "
            f"lines={total_exact}/{total_lines} ({accuracy:.1%})  "
            f"perfect_files={perfect_files}/{len(results)}  "
            f"time={total_time:.1f}s"
        )


if __name__ == "__main__":
    main()
