import argparse
from pathlib import Path

from app.pipeline.ocr.ocr_engines import OcrResult, SuryaOcrEngine
from app.pipeline.ocr.gotocr_normalizer import normalize_gotocr_text
from app.repo_paths import DEFAULT_EXACT_LINES_PATH
from app.validation.datasets import parse_labels
from app.validation.evaluation import print_summary, run_evaluation


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
        default=str(DEFAULT_EXACT_LINES_PATH),
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
    print_summary("surya", scores)


if __name__ == "__main__":
    main()
