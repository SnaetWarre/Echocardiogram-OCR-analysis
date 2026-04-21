from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.transcription.dead_space_char_splitter import split_dead_space_char_slices


def _default_charset() -> str:
    return "0123456789./-%cmLAoEVIDT"


def _canonical_chars(text: str) -> str:
    return "".join(ch for ch in str(text or "") if not ch.isspace())


def _safe_label_dirname(label: str) -> str:
    """Path segment for one class label; '/' and other reserved chars break pathlib on Windows."""
    if not label:
        return "_empty"
    if len(label) != 1:
        return "_multi_" + "_".join(f"{ord(ch):04x}" for ch in label)
    ch = label
    if ch in '\\/:*?"<>|' or ord(ch) < 32:
        return f"u{ord(ch):04x}"
    return ch


def _stable_ratio(key: str) -> float:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return value / float(0xFFFFFFFF)


def _render_line(text: str, *, height: int = 30, width_per_char: int = 18) -> np.ndarray:
    chars = _canonical_chars(text)
    width = max(48, len(chars) * width_per_char + 10)
    canvas = np.ones((height, width), dtype=np.uint8) * 255
    cv2.putText(canvas, chars, (4, int(height * 0.78)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, 0, 2, cv2.LINE_AA)
    return canvas


def _render_line_variant(text: str, rng: random.Random) -> np.ndarray:
    """Synthetic line render with randomized geometry (more diversity than a single template)."""
    chars = _canonical_chars(text)
    height = int(rng.choice([22, 24, 26, 28, 30]))
    width_per_char = int(rng.choice([16, 18, 20, 22, 24]))
    width = max(40, len(chars) * width_per_char + int(rng.randint(6, 14)))
    canvas = np.ones((height, width), dtype=np.uint8) * 255
    scale = float(rng.uniform(0.58, 0.9))
    thick = int(rng.choice([1, 2]))
    x0 = int(rng.randint(2, 10))
    y0 = int(height * float(rng.uniform(0.7, 0.84)))
    cv2.putText(
        canvas,
        chars,
        (x0, y0),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        0,
        thick,
        cv2.LINE_AA,
    )
    return canvas


def _to_gray_u8(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        return cv2.cvtColor(image.astype(np.uint8, copy=False), cv2.COLOR_BGR2GRAY)
    if image.ndim == 3:
        return image[..., 0].astype(np.uint8, copy=False)
    return image.astype(np.uint8, copy=False)


def _augment_char_crop(crop: np.ndarray, rng: random.Random) -> np.ndarray:
    """Photometric + mild geometric jitter (rotation, shift, scale) on a small char crop."""
    if crop.size == 0:
        return crop
    g = _to_gray_u8(crop)
    h, w = int(g.shape[0]), int(g.shape[1])
    if h >= 2 and w >= 2:
        center = (w * 0.5, h * 0.5)
        angle = rng.uniform(-11.0, 11.0)
        scale = rng.uniform(0.9, 1.12)
        M = cv2.getRotationMatrix2D(center, angle, scale)
        M[0, 2] += rng.uniform(-2.0, 2.0)
        M[1, 2] += rng.uniform(-2.0, 2.0)
        g = cv2.warpAffine(
            g,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )

    out = g.astype(np.float32)
    alpha = rng.uniform(0.85, 1.18)
    beta = rng.uniform(-14.0, 14.0)
    out = np.clip(out * alpha + beta, 0, 255).astype(np.uint8)

    if rng.random() < 0.45:
        sigma = rng.uniform(0.15, 1.15)
        k = 3 if min(out.shape[:2]) >= 3 else 1
        if k >= 3:
            out = cv2.GaussianBlur(out, (k, k), sigmaX=sigma)

    if rng.random() < 0.55:
        noise = rng.normalvariate(0.0, 7.0)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    if rng.random() < 0.12 and w > 4:
        dx = int(rng.choice((-1, 0, 1)))
        if dx != 0:
            out = np.roll(out, dx, axis=1)
            if dx > 0:
                out[:, :dx] = 255
            else:
                out[:, dx:] = 255

    return out


def _load_strings_from_label_scores(path: Path, *, include_mismatch_lines: bool) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    details = payload.get("file_details", []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    for file_item in details:
        if not isinstance(file_item, dict):
            continue
        file_path = str(file_item.get("file_path") or "")
        for match in file_item.get("matches", []):
            if not isinstance(match, dict):
                continue
            full_ok = bool(match.get("full_match", False))
            if not full_ok and not include_mismatch_lines:
                continue
            expected = str(match.get("expected_text") or "").strip()
            predicted = str(match.get("predicted_text") or match.get("pred_text") or "").strip()
            if not expected:
                continue
            rows.append(
                {
                    "source": "label_scores",
                    "file_path": file_path,
                    "expected_text": expected,
                    "predicted_text": predicted,
                    "full_match_line": full_ok,
                }
            )
    return rows


def _collect_label_scores_scan(scan_dir: Path, *, limit: int) -> list[Path]:
    if not scan_dir.is_dir():
        return []
    found = [p for p in scan_dir.rglob("label_scores.json") if p.is_file()]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    cap = max(1, int(limit))
    return found[:cap]


def _load_strings_from_validation_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            expected = str(row.get("expected_text") or row.get("expected") or "").strip()
            predicted = str(row.get("predicted_text") or row.get("predicted") or "").strip()
            if not expected:
                continue
            file_path = str(row.get("dicom_path") or row.get("file_path") or "")
            rows.append(
                {
                    "source": "validation_exact_failures",
                    "file_path": file_path,
                    "expected_text": expected,
                    "predicted_text": predicted,
                    "full_match_line": False,
                }
            )
    return rows


def _save_crop(crop: np.ndarray, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), crop)


def build_dataset(
    *,
    label_scores: Path,
    output_dir: Path,
    charset: str,
    validation_exact_failures_csv: Path | None = None,
    val_ratio: float = 0.15,
    min_split_confidence: float = 0.5,
    low_trust_confidence: float = 0.65,
    max_synthetic_ratio: float = 0.35,
    random_seed: int = 1337,
    real_augment_copies: int = 0,
    synthetic_rounds: int = 1,
    merge_label_scores: list[Path] | None = None,
    merge_scan_dir: Path | None = None,
    merge_scan_limit: int = 64,
    include_mismatch_lines: bool = False,
) -> dict[str, Any]:
    rng = random.Random(random_seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    merged_paths: list[str] = []
    seen_json: set[str] = set()
    source_rows: list[dict[str, Any]] = []

    def _merge_label_scores_file(path: Path) -> None:
        path = path.expanduser().resolve()
        key = str(path)
        if key in seen_json or not path.is_file():
            return
        seen_json.add(key)
        merged_paths.append(key)
        source_rows.extend(_load_strings_from_label_scores(path, include_mismatch_lines=include_mismatch_lines))

    _merge_label_scores_file(Path(label_scores))
    for extra in merge_label_scores or []:
        _merge_label_scores_file(Path(extra))
    if merge_scan_dir is not None:
        for hit in _collect_label_scores_scan(merge_scan_dir.expanduser().resolve(), limit=int(merge_scan_limit)):
            _merge_label_scores_file(hit)
    if include_mismatch_lines and validation_exact_failures_csv is not None and validation_exact_failures_csv.exists():
        source_rows.extend(_load_strings_from_validation_csv(validation_exact_failures_csv))

    # Dedupe by file+expected to keep deterministic, compact bootstrap.
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in source_rows:
        key = (str(row.get("file_path") or ""), str(row.get("expected_text") or ""))
        dedup[key] = row

    class_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    class_counts = Counter()

    for idx, row in enumerate(dedup.values()):
        expected_text = str(row.get("expected_text") or "")
        expected_chars = _canonical_chars(expected_text)
        if not expected_chars:
            continue

        rendered = _render_line(expected_text)
        split = split_dead_space_char_slices(rendered)
        split_ok = (
            split.expected_char_count == len(expected_chars)
            and split.confidence >= float(min_split_confidence)
            and len(split.slices) == len(expected_chars)
        )
        if not split_ok:
            rejected_rows.append(
                {
                    "file_path": row.get("file_path"),
                    "source": row.get("source"),
                    "expected_text": expected_text,
                    "predicted_text": row.get("predicted_text"),
                    "split_expected_char_count": split.expected_char_count,
                    "split_confidence": float(split.confidence),
                    "reject_reason": "split_mismatch_or_low_confidence",
                }
            )
            continue

        for char_index, (char_label, char_slice) in enumerate(zip(expected_chars, split.slices, strict=False)):
            if char_label not in charset:
                continue
            x1 = max(0, int(char_slice.x))
            y1 = max(0, int(char_slice.y))
            x2 = min(rendered.shape[1], x1 + int(char_slice.width))
            y2 = min(rendered.shape[0], y1 + int(char_slice.height))
            crop = rendered[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            sample_id = f"real_{idx:06d}_{char_index:02d}"
            crop_path = output_dir / "crops" / "real" / _safe_label_dirname(char_label) / f"{sample_id}.png"
            _save_crop(crop, crop_path)
            key = f"{row.get('file_path','')}|{expected_text}|{char_index}|{char_label}"
            split_name = "val" if _stable_ratio(key) < float(val_ratio) else "train"
            low_trust = float(split.confidence) < float(low_trust_confidence)
            base_row = {
                "sample_id": sample_id,
                "label": char_label,
                "split": split_name,
                "low_trust": bool(low_trust),
                "source": str(row.get("source") or "label_scores"),
                "file_path": str(row.get("file_path") or ""),
                "expected_text": expected_text,
                "predicted_text": str(row.get("predicted_text") or ""),
                "full_match_line": bool(row.get("full_match_line", False)),
                "split_confidence": float(split.confidence),
                "image_path": str(crop_path.relative_to(output_dir).as_posix()),
            }
            class_rows.append(base_row)
            class_counts[char_label] += 1

            for aug_i in range(max(0, int(real_augment_copies))):
                aug = _augment_char_crop(crop, rng)
                sample_id_a = f"real_{idx:06d}_{char_index:02d}_a{aug_i + 1:02d}"
                crop_path_a = output_dir / "crops" / "real" / _safe_label_dirname(char_label) / f"{sample_id_a}.png"
                _save_crop(aug, crop_path_a)
                row_a = dict(base_row)
                row_a["sample_id"] = sample_id_a
                row_a["image_path"] = str(crop_path_a.relative_to(output_dir).as_posix())
                row_a["low_trust"] = True
                class_rows.append(row_a)
                class_counts[char_label] += 1

    non_zero_counts = [count for count in class_counts.values() if count > 0]
    target_min = int(np.percentile(non_zero_counts, 20)) if non_zero_counts else 0
    max_synth_per_class = int(max(1, round(target_min * float(max_synthetic_ratio)))) if target_min > 0 else 12

    synthetic_rows: list[dict[str, Any]] = []
    for label in charset:
        have = int(class_counts.get(label, 0))
        needed = max(0, target_min - have)
        synth_count = min(needed, max_synth_per_class)
        if target_min == 0 and have == 0:
            synth_count = min(12, max_synth_per_class)
        rounds = max(1, int(synthetic_rounds))
        for round_i in range(rounds):
            for idx in range(synth_count):
                base = _render_line_variant(label, rng)
                crop = _augment_char_crop(base, rng)
                sample_id = f"synth_{ord(label):03d}_r{round_i}_{idx:04d}"
                crop_path = output_dir / "crops" / "synthetic" / _safe_label_dirname(label) / f"{sample_id}.png"
                _save_crop(crop, crop_path)
                split_name = "val" if _stable_ratio(f"synth|{label}|{round_i}|{idx}") < float(val_ratio) else "train"
                synthetic_rows.append(
                    {
                        "sample_id": sample_id,
                        "label": label,
                        "split": split_name,
                        "low_trust": True,
                        "source": "synthetic",
                        "file_path": "",
                        "expected_text": label,
                        "predicted_text": "",
                        "split_confidence": 0.0,
                        "image_path": str(crop_path.relative_to(output_dir).as_posix()),
                    }
                )
                class_counts[label] += 1

    rows = class_rows + synthetic_rows
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]

    manifest = {
        "source_label_scores": str(label_scores),
        "merged_label_scores_paths": merged_paths,
        "include_mismatch_lines": bool(include_mismatch_lines),
        "source_validation_exact_failures_csv": str(validation_exact_failures_csv) if validation_exact_failures_csv else "",
        "random_seed": int(random_seed),
        "real_augment_copies": int(real_augment_copies),
        "synthetic_rounds": int(synthetic_rounds),
        "charset": charset,
        "total_candidates": len(dedup),
        "accepted_samples": len(class_rows),
        "rejected_alignments": len(rejected_rows),
        "synthetic_samples": len(synthetic_rows),
        "class_balance": {label: int(class_counts.get(label, 0)) for label in charset},
        "rows": rows,
        "rejected_rows": rejected_rows,
    }

    train_manifest = {
        "charset": charset,
        "split": "train",
        "samples": train_rows,
    }
    val_manifest = {
        "charset": charset,
        "split": "val",
        "samples": val_rows,
    }

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "train_manifest.json").write_text(json.dumps(train_manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "val_manifest.json").write_text(json.dumps(val_manifest, indent=2) + "\n", encoding="utf-8")

    class_balance_md = ["# Class Balance", "", "| class | count |", "|---|---:|"]
    for label in charset:
        class_balance_md.append(f"| {label} | {int(class_counts.get(label, 0))} |")
    (output_dir / "class_balance.md").write_text("\n".join(class_balance_md) + "\n", encoding="utf-8")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap character fallback training datasets.")
    parser.add_argument(
        "--label-scores",
        type=Path,
        required=True,
        help="Primary label_scores.json (default: only full_match rows with expected_text).",
    )
    parser.add_argument(
        "--include-mismatch-lines",
        action="store_true",
        help="Also use non-full_match rows and --validation-exact-failures-csv (weaker char/crop alignment).",
    )
    parser.add_argument(
        "--merge-label-scores",
        type=Path,
        nargs="*",
        default=[],
        help="Additional label_scores.json files to merge (same row filter as primary).",
    )
    parser.add_argument(
        "--merge-scan-dir",
        type=Path,
        default=None,
        help="If set, merge rows from up to --merge-scan-limit newest label_scores.json under this directory.",
    )
    parser.add_argument(
        "--merge-scan-limit",
        type=int,
        default=64,
        help="Max label_scores.json files picked from --merge-scan-dir (newest first).",
    )
    parser.add_argument(
        "--validation-exact-failures-csv",
        type=Path,
        default=None,
        help="Optional path to validation_exact_failures CSV",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Output dataset directory")
    parser.add_argument("--charset", type=str, default=_default_charset(), help="Character set to include")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation split ratio")
    parser.add_argument("--min-split-confidence", type=float, default=0.5, help="Min split confidence")
    parser.add_argument("--low-trust-confidence", type=float, default=0.65, help="Low trust confidence threshold")
    parser.add_argument("--max-synthetic-ratio", type=float, default=0.5, help="Max synthetic ratio per class")
    parser.add_argument(
        "--real-augment-copies",
        type=int,
        default=8,
        help="Extra augmented PNGs per real char crop (rotation/shift/blur; 0 to disable).",
    )
    parser.add_argument(
        "--synthetic-rounds",
        type=int,
        default=2,
        help="Repeat synthetic generation rounds per class (more varied font renders).",
    )
    parser.add_argument("--random-seed", type=int, default=1337, help="Random seed")
    args = parser.parse_args()

    build_dataset(
        label_scores=args.label_scores,
        validation_exact_failures_csv=args.validation_exact_failures_csv,
        output_dir=args.output_dir,
        charset=str(args.charset),
        val_ratio=float(args.val_ratio),
        min_split_confidence=float(args.min_split_confidence),
        low_trust_confidence=float(args.low_trust_confidence),
        max_synthetic_ratio=float(args.max_synthetic_ratio),
        random_seed=int(args.random_seed),
        real_augment_copies=int(args.real_augment_copies),
        synthetic_rounds=int(args.synthetic_rounds),
        merge_label_scores=list(args.merge_label_scores) if args.merge_label_scores else [],
        merge_scan_dir=args.merge_scan_dir,
        merge_scan_limit=int(args.merge_scan_limit),
        include_mismatch_lines=bool(args.include_mismatch_lines),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
