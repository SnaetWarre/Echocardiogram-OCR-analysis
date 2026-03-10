import sys
import argparse
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.echo_ocr_eval_labels import (
    parse_labels,
    run_evaluation,
    _print_summary,
)
from app.pipeline.ocr_engines import OcrResult, SuryaOcrEngine
from app.pipeline.gotocr_normalizer import normalize_gotocr_text


class NormalizedSuryaEngine:
    def __init__(self) -> None:
        self._engine = SuryaOcrEngine()
        self.name = "surya (normalized)"

    def extract(self, image) -> OcrResult:
        result = self._engine.extract(image)
        normalized_text = normalize_gotocr_text(result.text)
        return OcrResult(
            text=normalized_text,
            confidence=result.confidence,
            tokens=result.tokens,
            engine_name=self.name,
        )


def _parse_split_filter(raw: str) -> set[str]:
    return {
        item.strip().lower()
        for item in raw.split(",")
        if item.strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels",
        default=str(PROJECT_ROOT / "labels" / "exact_lines.json"),
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Optional comma separated split filter (e.g. train,validation)",
    )
    parser.add_argument("--parser", default="regex")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    split_filter = _parse_split_filter(args.split)
    labeled_files = parse_labels(labels_path, split_filter=split_filter)

    if split_filter:
        print(f"Using split filter: {', '.join(sorted(split_filter))}")
    print(f"Parsed {len(labeled_files)} labeled files\n")

    engine = NormalizedSuryaEngine()

    print("\n--- Evaluating with: surya ---")

    class DummyArgs:
        def __init__(self, parser_name: str) -> None:
            self.parser = parser_name

    scores = run_evaluation(
        labeled_files,
        engine,
        verbose=True,
        args=DummyArgs(args.parser),
    )
    _print_summary("surya", scores)


if __name__ == "__main__":
    main()
