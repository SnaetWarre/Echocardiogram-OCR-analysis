from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.echo_ocr_eval_labels import parse_labels  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare line-level OCR training examples from exact lines")
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels" / "exact_lines.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "docs" / "ocr_redesign" / "line_training_data.jsonl"))
    parser.add_argument("--split", default="", help="Optional split filter")
    args = parser.parse_args()

    split_filter = {item.strip().lower() for item in args.split.split(",") if item.strip()}
    labeled_files = parse_labels(Path(args.labels), split_filter=split_filter)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for labeled_file in labeled_files:
            for measurement in labeled_file.measurements:
                payload = {
                    "file_name": labeled_file.file_name,
                    "file_path": str(labeled_file.path),
                    "split": labeled_file.split,
                    "order": measurement.order,
                    "exact_line": measurement.text,
                }
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
                count += 1

    print(f"Wrote {count} line-level examples to {output_path}")


if __name__ == "__main__":
    main()
