"""
Compare OCR engine outputs on the same ROI for labeled DICOM cases.

Runs PaddleOCR, EasyOCR, and Tesseract on the same crop and reports what each
engine reads. Use this to see where engines differ or fail.

Usage:
  python -m app.tools.echo_ocr_engine_compare --labels labels.md --out artifacts/ocr-eval/engine_compare.md
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.pipeline.echo_ocr_pipeline import (
    TopLeftBlueGrayBoxDetector,
    preprocess_roi,
)
from app.pipeline.ocr_engines import (
    OcrEngine,
    OcrResult,
    UnavailableOcrEngineError,
    build_engine,
)


def _get_roi_candidates(
    frame: np.ndarray,
    detector: TopLeftBlueGrayBoxDetector,
) -> List[Tuple[Tuple[int, int, int, int], float]]:
    """Same ROI candidates as EchoOcrPipeline._extract_measurements_for_frame."""
    candidates: List[Tuple[Tuple[int, int, int, int], float]] = []
    detection = detector.detect(frame)
    if detection.present and detection.bbox is not None:
        candidates.append((detection.bbox, max(0.2, detection.confidence)))

    h, w = frame.shape[:2]
    fallbacks = [
        (10, 5, int(w * 0.22), int(h * 0.10)),
        (10, 5, int(w * 0.26), int(h * 0.13)),
        (15, 10, int(w * 0.30), int(h * 0.16)),
        (0, 0, int(w * 0.35), int(h * 0.18)),
        (5, 0, int(w * 0.28), int(h * 0.12)),
        (0, 5, int(w * 0.32), int(h * 0.14)),
        (8, 8, int(w * 0.25), int(h * 0.11)),
    ]
    for x, y, bw, bh in fallbacks:
        x = max(0, min(x, w - 2))
        y = max(0, min(y, h - 2))
        bw = max(20, min(bw, w - x))
        bh = max(20, min(bh, h - y))
        candidates.append(((x, y, bw, bh), 0.15))
    return candidates


def _pick_best_roi(
    frame: np.ndarray,
    candidates: List[Tuple[Tuple[int, int, int, int], float]],
    engine: OcrEngine,
) -> Optional[Tuple[int, int, int, int]]:
    """Pick ROI with highest hint score (same logic as pipeline)."""
    best: Optional[Tuple[OcrResult, Tuple[int, int, int, int], float]] = None
    for bbox, base_conf in candidates:
        x, y, bw, bh = bbox
        roi = frame[y : y + bh, x : x + bw]
        prepared = preprocess_roi(roi)
        try:
            ocr = engine.extract(prepared)
        except Exception:
            continue
        text = ocr.text.lower()
        hint_score = 0.0
        for hint in ("pv", "tr", "mv", "vmax", "maxpg", "mmhg", "diam", "ef", "lv", "la"):
            if hint in text:
                hint_score += 0.5
        if any(u in text for u in ("m/s", "cm", "ml", "%")):
            hint_score += 0.3
        score = (len(ocr.tokens) * 1.2) + hint_score + (ocr.confidence * 0.5)
        if best is None or score > best[2]:
            best = (ocr, bbox, score)
    if best is None or best[2] < 1.2:
        return None
    return best[1]


def _run_engines_on_roi(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    engine_names: List[str],
) -> Dict[str, str]:
    """Run each available engine on the same ROI. Returns {engine_name: text}."""
    x, y, bw, bh = bbox
    roi = frame[y : y + bh, x : x + bw]
    prepared = preprocess_roi(roi)

    results: Dict[str, str] = {}
    for name in engine_names:
        try:
            engine = build_engine(name)
            ocr = engine.extract(prepared)
            results[name] = ocr.text.strip() or "(empty)"
        except (UnavailableOcrEngineError, Exception) as e:
            results[name] = f"(error: {e})"
    return results


def _parse_labels(path: Path) -> List[Path]:
    """Extract DICOM paths from labels.md."""
    lines = path.read_text(encoding="utf-8").splitlines()
    paths: List[Path] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("path:"):
            raw = stripped.split("path:", 1)[1].strip()
            p = Path(raw)
            if p.suffix.lower() == ".documents":
                p = p.with_suffix(".dcm")
            paths.append(p)
    return paths


def _format_report(
    rows: List[Dict[str, str]],
) -> str:
    lines = [
        "# OCR Engine Comparison",
        "",
        "Same ROI per case. Compare what each engine reads.",
        "",
        "| path | paddleocr | easyocr | tesseract |",
        "|------|-----------|---------|-----------|",
    ]
    for row in rows:
        path = row.get("path", "")
        paddle = (row.get("paddleocr") or "").replace("|", "\\|").replace("\n", " ")
        easy = (row.get("easyocr") or "").replace("|", "\\|").replace("\n", " ")
        tess = (row.get("tesseract") or "").replace("|", "\\|").replace("\n", " ")
        if len(paddle) > 60:
            paddle = paddle[:57] + "..."
        if len(easy) > 60:
            easy = easy[:57] + "..."
        if len(tess) > 60:
            tess = tess[:57] + "..."
        lines.append(f"| {path} | {paddle} | {easy} | {tess} |")

    lines.append("")
    lines.append("## Detailed view (full text)")
    lines.append("")
    for row in rows:
        path = row.get("path", "")
        lines.append(f"### {path}")
        lines.append("")
        for engine in ("paddleocr", "easyocr", "tesseract"):
            text = row.get(engine, "")
            lines.append(f"**{engine}:**")
            lines.append("```")
            lines.append(text)
            lines.append("```")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare OCR engine outputs on labeled DICOM cases."
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("labels.md"),
        help="Labels file with path: entries.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/ocr-eval/engine_compare.md"),
        help="Output report path.",
    )
    parser.add_argument(
        "--roi-picker",
        default="paddleocr",
        choices=["paddleocr", "easyocr", "tesseract"],
        help="Engine used to pick the best ROI (default: paddleocr).",
    )
    args = parser.parse_args()

    if not args.labels.exists():
        print(f"Labels file not found: {args.labels}")
        return 2

    paths = _parse_labels(args.labels)
    if not paths:
        print("No paths found in labels file.")
        return 1

    picker_engine = None
    for candidate in [args.roi_picker, "paddleocr", "tesseract", "easyocr"]:
        try:
            picker_engine = build_engine(candidate)
            if candidate != args.roi_picker:
                print(f"Using {candidate} for ROI picking (requested {args.roi_picker} unavailable)")
            break
        except UnavailableOcrEngineError:
            continue
    if picker_engine is None:
        print("No OCR engine available. Install paddleocr, tesseract, or easyocr.")
        return 2

    detector = TopLeftBlueGrayBoxDetector()
    engine_names = ["paddleocr", "easyocr", "tesseract"]
    rows: List[Dict[str, str]] = []

    for i, path in enumerate(paths):
        if not path.exists():
            print(f"[{i + 1}/{len(paths)}] Skip (missing): {path}")
            rows.append({
                "path": str(path),
                "paddleocr": "(file missing)",
                "easyocr": "(file missing)",
                "tesseract": "(file missing)",
            })
            continue

        print(f"[{i + 1}/{len(paths)}] {path.name}")
        try:
            series = load_dicom_series(path, load_pixels=True)
            frame = series.get_frame(0)
        except Exception as e:
            print(f"  Load error: {e}")
            rows.append({
                "path": str(path),
                "paddleocr": f"(load error: {e})",
                "easyocr": "",
                "tesseract": "",
            })
            continue

        candidates = _get_roi_candidates(frame, detector)
        bbox = _pick_best_roi(frame, candidates, picker_engine)
        if bbox is None:
            rows.append({
                "path": str(path),
                "paddleocr": "(no ROI with signal)",
                "easyocr": "",
                "tesseract": "",
            })
            continue

        results = _run_engines_on_roi(frame, bbox, engine_names)
        results["path"] = path.name
        rows.append(results)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = _format_report(rows)
    args.out.write_text(report, encoding="utf-8")
    print(f"\nReport written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
