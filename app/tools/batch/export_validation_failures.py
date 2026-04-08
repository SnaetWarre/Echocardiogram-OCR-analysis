"""Write validation_exact_failures.csv from a label_scores.json (full_match == false per line)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "label_scores_json",
        type=Path,
        help="Path to label_scores.json (e.g. .../gray_x3_lanczos/label_scores.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: sibling validation_exact_failures.csv next to label_scores.json).",
    )
    args = parser.parse_args()
    path = args.label_scores_json.expanduser().resolve()
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    out_path = args.output
    if out_path is None:
        out_path = path.parent.parent / "validation_exact_failures.csv"
    out_path = out_path.expanduser().resolve()

    rows: list[dict[str, object]] = []
    for fd in data.get("file_details", []):
        if fd.get("split") != "validation":
            continue
        fname = fd.get("file_name") or Path(fd.get("file_path", "")).name
        for i, m in enumerate(fd.get("matches") or []):
            if m.get("full_match", True):
                continue
            rows.append(
                {
                    "file_name": fname,
                    "line_index_in_matches": i,
                    "expected_text": m.get("expected_text", ""),
                    "predicted_text": m.get("predicted_text") or "",
                    "line_match": m.get("line_match"),
                    "value_match": m.get("value_match"),
                    "label_match": m.get("label_match"),
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "line_index_in_matches",
        "expected_text",
        "predicted_text",
        "line_match",
        "value_match",
        "label_match",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"Wrote {len(rows)} failure rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
