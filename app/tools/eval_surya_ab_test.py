from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.ocr.preprocessing import preprocess_roi as _original_preprocess_roi
from app.pipeline.gotocr_normalizer import normalize_gotocr_text
from app.pipeline.ocr_engines import OcrResult, SuryaOcrEngine
from app.repo_paths import DEFAULT_EXACT_LINES_PATH
from app.validation.datasets import parse_labels
from app.validation.evaluation import run_evaluation

DEFAULT_LABELS = DEFAULT_EXACT_LINES_PATH


class NormalizedSuryaEngine:
    def __init__(self) -> None:
        self._engine = SuryaOcrEngine()
        self.name = "surya (ab_test)"

    def extract(self, image) -> OcrResult:
        result = self._engine.extract(image)
        return OcrResult(
            text=normalize_gotocr_text(result.text),
            confidence=result.confidence,
            tokens=result.tokens,
            engine_name=self.name,
        )


def _parse_split_filter(raw: str) -> set[str]:
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


class _Args:
    def __init__(self, parser_name: str) -> None:
        self.parser = parser_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A/B test Surya OCR pre-processing parameters against exact-line JSON labels."
    )
    parser.add_argument(
        "--labels",
        default=str(DEFAULT_LABELS),
        help="Path to canonical JSON label file",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Comma separated split filter (e.g. train,validation)",
    )
    parser.add_argument(
        "--parser",
        default="regex",
        help="Parser mode (regex, local_llm)",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "ab_test_results.csv"),
        help="CSV file to write results to",
    )
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise SystemExit(f"Labels file not found: {labels_path}")

    split_filter = _parse_split_filter(args.split)
    labeled_files = parse_labels(labels_path, split_filter=split_filter)

    if split_filter:
        print(f"Split filter: {', '.join(sorted(split_filter))}")
    print(f"Loaded {len(labeled_files)} labeled files\n")

    engine = NormalizedSuryaEngine()

    grid: dict[str, list] = {
        "scale_factor": [2, 3],
        "scale_algo": ["cubic", "lanczos"],
        "contrast_mode": ["none", "clahe", "adaptive_threshold"],
    }

    keys = list(grid.keys())
    combinations = list(itertools.product(*(grid[k] for k in keys)))
    print(f"Starting A/B test: {len(combinations)} permutations\n")

    results: list[dict] = []

    for run_index, values in enumerate(combinations, start=1):
        params = dict(zip(keys, values))
        print(f"--- Run {run_index}/{len(combinations)} | {params}")

        def _proxy_preprocess(roi, _p=params):
            return _original_preprocess_roi(
                roi,
                scale_factor=_p["scale_factor"],
                scale_algo=_p["scale_algo"],
                contrast_mode=_p["contrast_mode"],
            )

        def _proxy_detector():
            return TopLeftBlueGrayBoxDetector()

        with (
            patch("app.validation.evaluation.preprocess_roi", side_effect=_proxy_preprocess),
            patch(
                "app.validation.evaluation.TopLeftBlueGrayBoxDetector",
                side_effect=_proxy_detector,
            ),
        ):
            scores = run_evaluation(
                labeled_files,
                engine,
                verbose=False,
                args=_Args(args.parser),
            )

        exact = scores["full_match_rate"]
        value = scores["value_match_rate"]
        elapsed = scores["elapsed_s"]

        print(f"  exact={exact:.1%}  value={value:.1%}  time={elapsed:.1f}s\n")

        results.append(
            {
                **params,
                "exact_match": exact,
                "value_match": value,
                "time_s": elapsed,
            }
        )

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=keys + ["exact_match", "value_match", "time_s"],
            )
            writer.writeheader()
            writer.writerows(results)

    print(f"Results saved to {args.output}")

    best_exact = max(results, key=lambda r: r["exact_match"])
    best_value = max(results, key=lambda r: r["value_match"])

    print("\n--- BEST EXACT MATCH ---")
    print(f"  {best_exact['exact_match']:.1%} with {{{', '.join(f'{k}={best_exact[k]}' for k in keys)}}}")

    print("\n--- BEST VALUE MATCH ---")
    print(f"  {best_value['value_match']:.1%} with {{{', '.join(f'{k}={best_value[k]}' for k in keys)}}}")


if __name__ == "__main__":
    main()
