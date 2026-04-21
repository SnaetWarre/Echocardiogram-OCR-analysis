from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload: {path}")
    return payload


def _mismatch_keys(label_scores: dict[str, Any]) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    details = label_scores.get("file_details", []) if isinstance(label_scores.get("file_details"), list) else []
    for file_item in details:
        if not isinstance(file_item, dict):
            continue
        file_path = str(file_item.get("file_path") or "")
        matches = file_item.get("matches", []) if isinstance(file_item.get("matches"), list) else []
        for match in matches:
            if not isinstance(match, dict):
                continue
            if bool(match.get("full_match", False)):
                continue
            expected = str(match.get("expected_text") or "")
            predicted = str(match.get("predicted_text") or "")
            out.add((file_path, expected, predicted))
    return out


def _summary_rate(payload: dict[str, Any], key: str) -> float:
    root = payload.get(key)
    if root is not None:
        return float(root)
    summary = payload.get("summary")
    if isinstance(summary, dict) and summary.get(key) is not None:
        return float(summary[key])
    return 0.0


def evaluate(*, baseline_path: Path, fallback_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    baseline = _load(baseline_path)
    fallback = _load(fallback_path)

    base_exact = _summary_rate(baseline, "exact_match_rate")
    fb_exact = _summary_rate(fallback, "exact_match_rate")
    base_value = _summary_rate(baseline, "value_match_rate")
    fb_value = _summary_rate(fallback, "value_match_rate")

    base_mismatches = _mismatch_keys(baseline)
    fb_mismatches = _mismatch_keys(fallback)
    corrected = base_mismatches - fb_mismatches
    regressed = fb_mismatches - base_mismatches

    result = {
        "baseline_path": str(baseline_path),
        "fallback_path": str(fallback_path),
        "exact_match_rate": {
            "baseline": base_exact,
            "fallback": fb_exact,
            "delta": fb_exact - base_exact,
        },
        "value_match_rate": {
            "baseline": base_value,
            "fallback": fb_value,
            "delta": fb_value - base_value,
        },
        "corrected_mismatch_count": len(corrected),
        "regressed_mismatch_count": len(regressed),
        "corrected_examples": [
            {"file_path": file_path, "expected_text": expected, "baseline_predicted": predicted}
            for file_path, expected, predicted in sorted(corrected)[:100]
        ],
        "regressed_examples": [
            {"file_path": file_path, "expected_text": expected, "fallback_predicted": predicted}
            for file_path, expected, predicted in sorted(regressed)[:100]
        ],
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline vs char-fallback label score outputs.")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline label_scores.json")
    parser.add_argument("--fallback", type=Path, required=True, help="Fallback label_scores.json")
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    result = evaluate(baseline_path=args.baseline, fallback_path=args.fallback, output_path=args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
