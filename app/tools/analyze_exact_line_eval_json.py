"""Summarize exact-line eval JSON: mismatches, flags, and coarse failure patterns."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _measurement_stem(expected_line: str) -> str:
    """First 2–4 tokens of the label side (rough proxy for measurement type)."""
    line = re.sub(r"^\d+\s+", "", expected_line.strip())
    parts = line.split()
    if len(parts) >= 3:
        return " ".join(parts[:3])
    return " ".join(parts) if parts else expected_line[:40]


def _bucket(match: dict[str, Any]) -> str:
    if match.get("full_match"):
        return "full_match"
    pred = match.get("predicted_text")
    if pred is None or str(pred).strip() == "":
        return "missing_or_empty_prediction"
    lm = bool(match.get("label_match"))
    vm = bool(match.get("value_match"))
    um = bool(match.get("unit_match"))
    pm = bool(match.get("prefix_match"))
    if lm and vm and um and pm:
        return "partial_line_text_only"
    if lm and vm and not um:
        return "wrong_unit"
    if lm and not vm:
        return "wrong_value_same_label"
    if not lm and vm:
        return "wrong_label_same_value"
    if not lm and not vm:
        return "wrong_label_and_value"
    return "other_mismatch"


def _report_roi_failures(engine_name: str, payload: dict[str, Any]) -> None:
    """Files where no frame had a measurement-box ROI (TopLeftBlueGrayBoxDetector)."""
    details = payload.get("file_details")
    if not isinstance(details, list):
        return

    no_roi: list[tuple[str, str, str, int, int]] = []
    for file_row in details:
        if not isinstance(file_row, dict):
            continue
        fname = str(file_row.get("file_name", ""))
        split = str(file_row.get("split", ""))
        fpath = str(file_row.get("file_path", ""))
        pred_n = int(file_row.get("predicted_count", 0) or 0)
        frames = file_row.get("frames")
        if not isinstance(frames, list):
            continue
        n_frames = len(frames)
        roi_frames = sum(
            1
            for fr in frames
            if isinstance(fr, dict) and fr.get("roi_bbox") is not None
        )
        if roi_frames == 0:
            no_roi.append((fname, split, fpath, n_frames, pred_n))

    if not no_roi:
        return

    print(f"\n{'=' * 72}")
    print(f"[{engine_name}] Panel ROI never found (TopLeftBlueGrayBoxDetector, all frames)")
    print(f"  Count: {len(no_roi)} file(s) — OCR never ran (no #1A2129-colored box match).")
    for fname, split, fpath, n_frames, pred_n in no_roi:
        print(f"  [{split}] {fname}  frames={n_frames} predicted_count={pred_n}")
        if fpath:
            print(f"    path: {fpath}")


def _analyze_engine(engine_name: str, payload: dict[str, Any]) -> None:
    details = payload.get("file_details")
    if not isinstance(details, list):
        print(f"[{engine_name}] No file_details in JSON; re-run eval with --json-out")
        return

    _report_roi_failures(engine_name, payload)

    mismatches: list[tuple[str, str, str, dict[str, Any]]] = []
    bucket_counts: Counter[str] = Counter()
    stem_counts: Counter[str] = Counter()
    split_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for file_row in details:
        if not isinstance(file_row, dict):
            continue
        fname = str(file_row.get("file_name", ""))
        split = str(file_row.get("split", ""))
        matches = file_row.get("matches")
        if not isinstance(matches, list):
            continue
        for m in matches:
            if not isinstance(m, dict):
                continue
            if m.get("full_match"):
                continue
            b = _bucket(m)
            bucket_counts[b] += 1
            exp = str(m.get("expected_text") or "")
            stem_counts[_measurement_stem(exp)] += 1
            split_counts[split][b] += 1
            mismatches.append((fname, split, b, m))

    total_labels = int(payload.get("total_labels", 0) or 0)
    full = int(payload.get("total_full_match", 0) or 0)
    rate = payload.get("full_match_rate")
    print(f"\n{'=' * 72}")
    print(f"Engine: {engine_name}")
    if total_labels:
        print(f"Exact line accuracy: {full}/{total_labels} ({float(rate) * 100:.2f}%)" if rate is not None else f"Exact: {full}/{total_labels}")
    print(f"Mismatched lines: {len(mismatches)}")
    print("\n--- Failure buckets (counts) ---")
    for name, count in bucket_counts.most_common():
        print(f"  {count:4d}  {name}")

    print("\n--- Top stems among failing lines (heuristic) ---")
    for stem, count in stem_counts.most_common(15):
        print(f"  {count:4d}  {stem}")

    if split_counts:
        print("\n--- Mismatches by dataset split ---")
        for split in sorted(split_counts.keys()):
            c = split_counts[split]
            total = sum(c.values())
            print(f"  [{split}] total={total}")
            for b, n in c.most_common(8):
                print(f"      {n:4d}  {b}")

    print("\n--- Per-row mismatches (expected vs predicted) ---")
    for fname, split, b, m in mismatches:
        exp = m.get("expected_text")
        pred = m.get("predicted_text")
        flags = (
            f"L={int(bool(m.get('label_match')))} "
            f"V={int(bool(m.get('value_match')))} "
            f"U={int(bool(m.get('unit_match')))} "
            f"P={int(bool(m.get('prefix_match')))}"
        )
        pred_s = pred if pred is not None else "<none>"
        print(f"  [{split}] {fname}")
        print(f"    bucket={b}  {flags}")
        print(f"    expected:  {exp}")
        print(f"    predicted: {pred_s}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "json_path",
        type=Path,
        help="JSON written by echo_ocr_eval_labels --json-out",
    )
    ap.add_argument(
        "--engine",
        default="",
        help="Key inside JSON (e.g. glm-ocr). Default: single key or glm-ocr if present.",
    )
    args = ap.parse_args()
    path = args.json_path
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Top-level JSON must be an object")

    keys = list(data.keys())
    chosen = args.engine.strip()
    if not chosen:
        if len(keys) == 1:
            chosen = keys[0]
        elif "glm-ocr" in data:
            chosen = "glm-ocr"
        else:
            raise SystemExit(f"Multiple engines in JSON; pass --engine one of: {', '.join(keys)}")

    if chosen not in data:
        raise SystemExit(f"No key {chosen!r} in JSON (have: {', '.join(keys)})")

    payload = data[chosen]
    if not isinstance(payload, dict):
        raise SystemExit(f"Payload for {chosen!r} must be an object")

    _analyze_engine(chosen, payload)


if __name__ == "__main__":
    main()
