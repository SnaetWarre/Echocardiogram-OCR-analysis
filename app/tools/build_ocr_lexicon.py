from __future__ import annotations

import argparse
from pathlib import Path

from app.pipeline.lexicon_builder import build_lexicon_artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a reusable OCR lexicon/statistics artifact from exact_lines.json"
    )
    parser.add_argument(
        "--labels",
        default="labels/exact_lines.json",
        help="Path to the exact-line labels JSON",
    )
    parser.add_argument(
        "--output",
        default="docs/ocr_redesign/exact_lines_lexicon.json",
        help="Output artifact path",
    )
    args = parser.parse_args()

    labels_path = Path(args.labels)
    output_path = Path(args.output)
    artifact = build_lexicon_artifact(labels_path)
    artifact.save(output_path)
    print(f"Wrote lexicon artifact to {output_path}")
    print(f"Files: {artifact.total_files}")
    print(f"Lines: {artifact.total_lines}")
    print(f"Unique exact lines: {len(artifact.exact_line_frequencies)}")
    print(f"Unique label families: {len(artifact.label_frequencies)}")


if __name__ == "__main__":
    main()
