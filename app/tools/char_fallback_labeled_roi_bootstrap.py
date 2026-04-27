"""Build char training crops from *real* DICOM line ROIs using ``label_scores`` + ``labels.json`` paths.

Default: **only** ``matches[]`` rows with ``full_match`` and non-empty ``expected_text``, so each
character label is paired with a line the sweep already read end-to-end correctly (safer alignment
than using gold text on lines where OCR disagrees). Pass ``--include-mismatch-lines`` to also add
non-``full_match`` rows (optional hard-mining; alignment is less trustworthy).

Unlike ``char_fallback_dataset_bootstrap`` (OpenCV renders of ``expected_text``), this loads each
DICOM, runs the same ``gray_x3_lanczos`` stack as the headless GLM sweep when possible, maps
``matches[i]`` to a panel line, runs ``split_dead_space_char_slices`` on the raw line crop, and
saves one PNG per character labeled from ``expected_text``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import (
    DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX,
    DEFAULT_SEGMENTATION_MODE,
    DEFAULT_TARGET_LINE_HEIGHT_PX,
)
from app.pipeline.layout.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.layout.line_segmenter import LineSegmenter
from app.pipeline.ocr.ocr_engines import UnavailableOcrEngineError, build_engine
from app.pipeline.transcription.line_transcriber import crop_segment
from app.pipeline.transcription.vertical_slicer import CharSlice, VerticalSliceResult, slice_line_into_vertical_slices
from app.tools.batch.sweep_preprocessing_headless import _broad_configs, _build_preprocess_views
from app.tools.char_fallback_dataset_bootstrap import (
    _augment_char_crop,
    _canonical_chars,
    _default_charset,
    _safe_label_dirname,
)
from app.validation.datasets import resolve_dataset_path


def _count_mismatch_rows(details: list[Any], split_filter: str) -> int:
    n = 0
    for fd in details:
        if not isinstance(fd, dict) or str(fd.get("split") or "") != split_filter:
            continue
        for m in fd.get("matches", []) if isinstance(fd.get("matches"), list) else []:
            if isinstance(m, dict) and not bool(m.get("full_match", False)):
                n += 1
    return n


def _count_scored_match_rows(details: list[Any], split_filter: str) -> int:
    """Matches with non-empty expected_text in split (candidates for ROI crops)."""
    n = 0
    for fd in details:
        if not isinstance(fd, dict) or str(fd.get("split") or "") != split_filter:
            continue
        for m in fd.get("matches", []) if isinstance(fd.get("matches"), list) else []:
            if not isinstance(m, dict):
                continue
            if str(m.get("expected_text") or "").strip():
                n += 1
    return n


def _uniform_ink_span_split(
    line_image: np.ndarray,
    expected_char_count: int,
    *,
    min_split_confidence: float,
) -> VerticalSliceResult | None:
    """When column-based dead space does not yield one box per label char, split the ink span evenly."""
    if expected_char_count <= 0:
        return None
    gray = line_image if line_image.ndim == 2 else cv2.cvtColor(line_image[..., :3], cv2.COLOR_BGR2GRAY)
    gray = gray.astype(np.uint8, copy=False)
    h, w = gray.shape[:2]
    if h < 2 or w < 2:
        return None
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_cols = (binary > 0).any(axis=0)
    if not bool(ink_cols.any()):
        x0, x1 = 0, w
    else:
        xs = np.flatnonzero(ink_cols)
        x0, x1 = int(xs[0]), int(xs[-1]) + 1
    span = max(1, x1 - x0)
    n = int(expected_char_count)
    slices: list[CharSlice] = []
    for i in range(n):
        xi0 = x0 + (span * i) // n
        xi1 = x0 + (span * (i + 1)) // n
        xi1 = max(xi0 + 1, xi1)
        sub = binary[:, xi0:xi1]
        ys = np.flatnonzero(sub.any(axis=1))
        if ys.size:
            y1, y2 = int(ys[0]), int(ys[-1]) + 1
        else:
            y1, y2 = 0, h
        ink_density = float((sub[y1:y2, :] > 0).mean()) if y2 > y1 else 0.0
        slices.append(
            CharSlice(
                x=int(xi0),
                y=0,
                width=max(1, int(xi1 - xi0)),
                height=int(h),
                ink_density=ink_density,
                local_ink_top=int(y1),
                local_ink_bottom=int(y2),
            )
        )
    return VerticalSliceResult(
        preprocessed_line=gray,
        binary_mask=binary,
        slices=tuple(slices),
        expected_char_count=len(slices),
        confidence=float(min_split_confidence),
        reliable=True,
        gap_count=max(0, n - 1),
        gap_widths=tuple(max(0, slices[idx].x - (slices[idx - 1].x + slices[idx - 1].width)) for idx in range(1, len(slices))),
        space_after=tuple(False for _ in range(max(0, len(slices) - 1))),
        space_gap_threshold_px=0,
        cut_columns=tuple(int(sl.x + sl.width) for sl in slices[:-1]),
    )


def _stable_ratio(key: str) -> float:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return value / float(0xFFFFFFFF)


def _save_crop(crop: np.ndarray, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), crop)


def _try_build_pipeline(config_name: str):
    from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline

    sweep_cfg = next(c for c in _broad_configs() if c.name == config_name)
    preprocess_views = _build_preprocess_views(sweep_cfg)
    try:
        pipe = EchoOcrPipeline(
            ocr_engine=build_engine("glm-ocr"),
            config=PipelineConfig(
                parameters={
                    "ocr_engine": "glm-ocr",
                    "requested_ocr_engine": "glm-ocr",
                    "parser_mode": "off",
                }
            ),
        )
        pipe.ensure_components()
        pipe._line_transcriber.preprocess_views = preprocess_views
        return pipe, sweep_cfg.name
    except (UnavailableOcrEngineError, Exception):
        return None, sweep_cfg.name


def build_labeled_roi_dataset(
    *,
    labels_json: Path,
    label_scores: Path,
    output_dir: Path,
    charset: str,
    split_filter: str = "validation",
    val_ratio: float = 0.12,
    min_split_confidence: float = 0.45,
    real_augment_copies: int = 16,
    random_seed: int = 1337,
    sweep_config_name: str = "gray_x3_lanczos",
    uniform_split_fallback: bool = False,
    include_mismatch_lines: bool = False,
) -> dict[str, Any]:
    rng = random.Random(int(random_seed))
    output_dir.mkdir(parents=True, exist_ok=True)

    ls = json.loads(Path(label_scores).read_text(encoding="utf-8"))
    details = ls.get("file_details", []) if isinstance(ls.get("file_details"), list) else []
    mismatch_rows_in_split = _count_mismatch_rows(details, split_filter)
    candidate_match_rows_in_split = _count_scored_match_rows(details, split_filter)

    pipe, _cfg_name = _try_build_pipeline(sweep_config_name)
    detector = TopLeftBlueGrayBoxDetector()
    segmenter = LineSegmenter(
        segmentation_mode=DEFAULT_SEGMENTATION_MODE,
        target_line_height_px=DEFAULT_TARGET_LINE_HEIGHT_PX,
        extra_left_pad_px=DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX,
    )

    class_rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    uniform_fallback_lines = 0

    sample_seq = 0
    for fd in details:
        if not isinstance(fd, dict):
            continue
        if str(fd.get("split") or "") != split_filter:
            continue
        dicom_path = resolve_dataset_path(fd, labels_json)
        if not dicom_path.is_file():
            rejected.append({"file_path": str(dicom_path), "reason": "missing_dicom"})
            continue

        matches = fd.get("matches", []) if isinstance(fd.get("matches"), list) else []
        try:
            series = load_dicom_series(dicom_path, load_pixels=True)
            frame = series.raw_frames[0]
        except Exception as exc:
            rejected.append({"file_path": str(dicom_path), "reason": f"load_error:{exc}"})
            continue

        detection = detector.detect(frame)
        if not detection.present or detection.bbox is None:
            rejected.append({"file_path": str(dicom_path), "reason": "no_roi"})
            continue

        x, y, bw, bh = detection.bbox
        roi = frame[y : y + bh, x : x + bw].copy()

        panel = None
        measurements: list[Any] = []
        segmentation = segmenter.segment(roi, tokens=None)
        if pipe is not None:
            try:
                _det, segmentation, _ocr, panel, measurements, _bbox = pipe.analyze_frame_with_debug(frame)
            except Exception:
                segmentation = segmenter.segment(roi, tokens=None)
                panel = None
                measurements = []

        usable = list(segmentation.lines)
        if not usable:
            rejected.append({"file_path": str(dicom_path), "reason": "no_lines"})
            continue

        match_to_panel: dict[int, int] = {}
        if measurements:
            for match_ix, measurement in enumerate(measurements):
                hint = getattr(measurement, "order_hint", None)
                if hint is None:
                    continue
                p_ix = int(hint)
                if 0 <= p_ix < len(usable):
                    match_to_panel[int(match_ix)] = p_ix

        for match_ix, match in enumerate(matches):
            if not isinstance(match, dict):
                continue
            if not bool(match.get("full_match", False)) and not include_mismatch_lines:
                continue
            expected_raw = str(match.get("expected_text") or "").strip()
            if not expected_raw:
                continue
            expected_chars = _canonical_chars(expected_raw)
            if not expected_chars:
                continue

            panel_ix = match_to_panel.get(match_ix)
            if panel_ix is None:
                if match_ix < len(usable):
                    panel_ix = int(match_ix)
                else:
                    rejected.append(
                        {
                            "file_path": str(dicom_path),
                            "match_ix": match_ix,
                            "expected_text": expected_raw,
                            "reason": "unmapped_match_index",
                        }
                    )
                    continue

            if panel_ix < 0 or panel_ix >= len(usable):
                rejected.append(
                    {
                        "file_path": str(dicom_path),
                        "match_ix": match_ix,
                        "reason": "panel_index_range",
                    }
                )
                continue

            raw_line = crop_segment(roi, usable[panel_ix])
            if raw_line.size == 0:
                continue

            split = slice_line_into_vertical_slices(raw_line)
            split_method = "dead_space"
            if (
                split.expected_char_count != len(expected_chars)
                or len(split.slices) != len(expected_chars)
                or float(split.confidence) < float(min_split_confidence)
            ):
                if bool(uniform_split_fallback):
                    fb = _uniform_ink_span_split(
                        raw_line,
                        len(expected_chars),
                        min_split_confidence=float(min_split_confidence),
                    )
                    if fb is not None and len(fb.slices) == len(expected_chars):
                        split = fb
                        split_method = "uniform_ink_span"
                        uniform_fallback_lines += 1
                    else:
                        rejected.append(
                            {
                                "file_path": str(dicom_path),
                                "match_ix": match_ix,
                                "expected_text": expected_raw,
                                "split_expected": split.expected_char_count,
                                "label_chars": len(expected_chars),
                                "slices": len(split.slices),
                                "split_confidence": float(split.confidence),
                                "reason": "split_mismatch_or_low_confidence",
                            }
                        )
                        continue
                else:
                    rejected.append(
                        {
                            "file_path": str(dicom_path),
                            "match_ix": match_ix,
                            "expected_text": expected_raw,
                            "split_expected": split.expected_char_count,
                            "label_chars": len(expected_chars),
                            "slices": len(split.slices),
                            "split_confidence": float(split.confidence),
                            "reason": "split_mismatch_or_low_confidence",
                        }
                    )
                    continue

            for char_index, (char_label, char_slice) in enumerate(zip(expected_chars, split.slices, strict=False)):
                if char_label not in charset:
                    continue
                x1 = max(0, int(char_slice.x))
                y1 = max(0, int(char_slice.y))
                x2 = min(raw_line.shape[1], x1 + int(char_slice.width))
                y2 = min(raw_line.shape[0], y1 + int(char_slice.height))
                crop = raw_line[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                key = f"{dicom_path}|{match_ix}|{char_index}|{char_label}"
                split_name = "val" if _stable_ratio(key) < float(val_ratio) else "train"
                sample_id = f"roi_{sample_seq:06d}_{char_index:02d}"
                sample_seq += 1
                crop_path = output_dir / "crops" / "labeled_roi" / _safe_label_dirname(char_label) / f"{sample_id}.png"
                _save_crop(crop, crop_path)
                row = {
                    "sample_id": sample_id,
                    "label": char_label,
                    "split": split_name,
                    "low_trust": float(split.confidence) < 0.65 or split_method != "dead_space",
                    "source": "labeled_roi",
                    "full_match_line": bool(match.get("full_match", False)),
                    "split_method": split_method,
                    "file_path": str(dicom_path),
                    "expected_text": expected_raw,
                    "predicted_text": str(match.get("predicted_text") or match.get("pred_text") or ""),
                    "split_confidence": float(split.confidence),
                    "image_path": str(crop_path.relative_to(output_dir).as_posix()),
                    "match_index": int(match_ix),
                    "panel_line_index": int(panel_ix),
                }
                class_rows.append(row)
                class_counts[char_label] += 1

                for aug_i in range(max(0, int(real_augment_copies))):
                    aug = _augment_char_crop(crop, rng)
                    sample_id_a = f"{sample_id}_a{aug_i + 1:02d}"
                    crop_path_a = output_dir / "crops" / "labeled_roi" / _safe_label_dirname(char_label) / f"{sample_id_a}.png"
                    _save_crop(aug, crop_path_a)
                    row_a = dict(row)
                    row_a["sample_id"] = sample_id_a
                    row_a["image_path"] = str(crop_path_a.relative_to(output_dir).as_posix())
                    row_a["low_trust"] = True
                    row_a["source"] = "labeled_roi_aug"
                    class_rows.append(row_a)
                    class_counts[char_label] += 1

    train_rows = [r for r in class_rows if r["split"] == "train"]
    val_rows = [r for r in class_rows if r["split"] == "val"]

    manifest = {
        "kind": "labeled_roi_char_bootstrap",
        "labels_json": str(labels_json),
        "label_scores": str(label_scores),
        "split_filter": split_filter,
        "sweep_config_name": sweep_config_name,
        "charset": charset,
        "mismatch_rows_in_split": int(mismatch_rows_in_split),
        "candidate_match_rows_in_split": int(candidate_match_rows_in_split),
        "include_mismatch_lines": bool(include_mismatch_lines),
        "uniform_split_fallback_enabled": bool(uniform_split_fallback),
        "uniform_fallback_lines": int(uniform_fallback_lines),
        "accepted_samples": len(class_rows),
        "rejected": rejected,
        "class_balance": {c: int(class_counts.get(c, 0)) for c in charset},
        "rows": class_rows,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "train_manifest.json").write_text(
        json.dumps({"charset": charset, "split": "train", "samples": train_rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "val_manifest.json").write_text(
        json.dumps({"charset": charset, "split": "val", "samples": val_rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-json", type=Path, default=Path("labels/labels.json"), help="labels.json for DICOM path resolution")
    parser.add_argument("--label-scores", type=Path, required=True, help="label_scores.json (e.g. charfb or v4 sweep)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--charset", type=str, default=_default_charset())
    parser.add_argument("--split", type=str, default="validation", help="file_details split filter")
    parser.add_argument("--val-ratio", type=float, default=0.12)
    parser.add_argument("--min-split-confidence", type=float, default=0.45)
    parser.add_argument("--real-augment-copies", type=int, default=16)
    parser.add_argument("--random-seed", type=int, default=1337)
    parser.add_argument(
        "--sweep-config-name",
        type=str,
        default="gray_x3_lanczos",
        help="Must match preprocess used in the sweep you compare against.",
    )
    parser.add_argument(
        "--uniform-split-fallback",
        action="store_true",
        help="If dead-space column count != label length, split the ink span into equal slots (noisier crops, more recall).",
    )
    parser.add_argument(
        "--include-mismatch-lines",
        action="store_true",
        help="Also use matches where full_match is false (optional; weaker char/crop alignment).",
    )
    args = parser.parse_args()

    manifest = build_labeled_roi_dataset(
        labels_json=args.labels_json.expanduser().resolve(),
        label_scores=args.label_scores.expanduser().resolve(),
        output_dir=args.output_dir.expanduser().resolve(),
        charset=str(args.charset),
        split_filter=str(args.split),
        val_ratio=float(args.val_ratio),
        min_split_confidence=float(args.min_split_confidence),
        real_augment_copies=int(args.real_augment_copies),
        random_seed=int(args.random_seed),
        sweep_config_name=str(args.sweep_config_name),
        uniform_split_fallback=bool(args.uniform_split_fallback),
        include_mismatch_lines=bool(args.include_mismatch_lines),
    )
    print(
        json.dumps(
            {
                "mismatch_rows_in_split": manifest.get("mismatch_rows_in_split"),
                "candidate_match_rows_in_split": manifest.get("candidate_match_rows_in_split"),
                "include_mismatch_lines": manifest.get("include_mismatch_lines"),
                "accepted_samples": manifest.get("accepted_samples"),
                "uniform_fallback_lines": manifest.get("uniform_fallback_lines"),
                "class_balance": manifest.get("class_balance"),
            },
            indent=2,
        )
    )
    rej = manifest.get("rejected", [])
    print("rejected_count:", len(rej))
    if rej:
        by_reason = Counter(str(r.get("reason") or "?") for r in rej if isinstance(r, dict))
        print("rejected_by_reason:", json.dumps(dict(by_reason)))
        print("first_rejection:", json.dumps(rej[0], indent=2) if isinstance(rej[0], dict) else rej[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
