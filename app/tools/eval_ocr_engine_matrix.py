from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector  # noqa: E402
from app.pipeline.echo_ocr_pipeline import preprocess_roi  # noqa: E402
from app.pipeline.ocr_engines import build_engine  # noqa: E402
from app.tools.echo_ocr_eval_labels import parse_labels, run_evaluation  # noqa: E402


_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_TOKEN_RE = re.compile(r"[A-Za-z0-9%']+")


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace(",", ".").strip())
    except Exception:
        return None


def _value_in_text(expected_value: str, text: str, tol: float = 0.011) -> bool:
    expected = _to_float(expected_value)
    if expected is None:
        return expected_value.strip() in text
    for raw in _NUM_RE.findall(text):
        parsed = _to_float(raw)
        if parsed is not None and abs(parsed - expected) <= tol:
            return True
    return False


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = unit.strip().lower()
    if not normalized:
        return None
    aliases = {
        "mmhg": "mmhg",
        "m/s": "m/s",
        "cm/s": "cm/s",
        "m/s2": "m/s2",
        "cm": "cm",
        "mm": "mm",
        "ms": "ms",
        "s": "s",
        "%": "%",
        "ml": "ml",
        "cm2": "cm2",
        "ml/m2": "ml/m2",
        "bpm": "bpm",
    }
    return aliases.get(normalized, normalized)


def _line_contains_unit(line: str, unit: str | None) -> bool:
    if unit is None:
        return True
    norm_line = line.lower().replace(" ", "")
    norm_unit = unit.lower().replace(" ", "")
    return norm_unit in norm_line


def _name_tokens(name: str) -> list[str]:
    tokens = [t.lower() for t in _TOKEN_RE.findall(name)]
    return [t for t in tokens if len(t) >= 2]


def _line_name_match(line: str, expected_name: str) -> bool:
    line_norm = line.lower()
    tokens = _name_tokens(expected_name)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in line_norm)
    required_hits = 1 if len(tokens) <= 2 else 2
    return hits >= required_hits


@dataclass
class RawEvalScores:
    total_files: int
    files_with_box: int
    files_with_text: int
    total_labels: int
    value_hits: int
    name_value_hits: int
    full_hits: int
    elapsed_s: float

    @property
    def box_detect_rate(self) -> float:
        return self.files_with_box / max(self.total_files, 1)

    @property
    def text_detect_rate(self) -> float:
        return self.files_with_text / max(self.total_files, 1)

    @property
    def value_hit_rate(self) -> float:
        return self.value_hits / max(self.total_labels, 1)

    @property
    def name_value_hit_rate(self) -> float:
        return self.name_value_hits / max(self.total_labels, 1)

    @property
    def full_hit_rate(self) -> float:
        return self.full_hits / max(self.total_labels, 1)


class _Args:
    def __init__(self, parser: str):
        self.parser = parser


def run_raw_text_eval(labels, engine) -> RawEvalScores:
    detector = TopLeftBlueGrayBoxDetector()

    total_files = 0
    files_with_box = 0
    files_with_text = 0
    total_labels = 0
    value_hits = 0
    name_value_hits = 0
    full_hits = 0

    started = time.perf_counter()

    for labeled_file in labels:
        if not labeled_file.path.exists():
            continue
        total_files += 1
        total_labels += len(labeled_file.measurements)

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception:
            continue

        file_has_box = False
        file_has_text = False
        all_lines: list[str] = []
        all_text_chunks: list[str] = []

        for frame_idx in range(series.frame_count):
            frame = series.get_frame(frame_idx)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                continue
            file_has_box = True

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            prepared = preprocess_roi(roi)
            ocr_result = engine.extract(prepared)
            text = (ocr_result.text or "").strip()
            if text:
                file_has_text = True
                all_text_chunks.append(text)
                all_lines.extend(line.strip() for line in text.splitlines() if line.strip())

        if file_has_box:
            files_with_box += 1
        if file_has_text:
            files_with_text += 1

        merged_text = "\n".join(all_text_chunks).lower().replace(",", ".")
        normalized_lines = [line.lower().replace(",", ".") for line in all_lines]

        for measurement in labeled_file.measurements:
            expected_unit = _normalize_unit(measurement.unit)

            if _value_in_text(measurement.value, merged_text):
                value_hits += 1

            name_value_matched = False
            full_matched = False
            for line in normalized_lines:
                if not _value_in_text(measurement.value, line):
                    continue
                if not _line_name_match(line, measurement.name):
                    continue
                name_value_matched = True
                if _line_contains_unit(line, expected_unit):
                    full_matched = True
                    break

            if name_value_matched:
                name_value_hits += 1
            if full_matched:
                full_hits += 1

    elapsed_s = time.perf_counter() - started

    return RawEvalScores(
        total_files=total_files,
        files_with_box=files_with_box,
        files_with_text=files_with_text,
        total_labels=total_labels,
        value_hits=value_hits,
        name_value_hits=name_value_hits,
        full_hits=full_hits,
        elapsed_s=elapsed_s,
    )


def format_rate(value: float) -> str:
    return f"{value:.1%}"


def _parser_label(parser_mode: str) -> str:
    if parser_mode == "regex":
        return "regex_parser"
    if parser_mode == "local_llm":
        return "local_llm_parser"
    return f"{parser_mode}_parser"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OCR engine comparison matrix on labels")
    parser.add_argument("--labels", default=str(PROJECT_ROOT / "labels.md"))
    parser.add_argument(
        "--engines",
        default="easyocr,tesseract,paddleocr,surya",
        help="Comma separated engines",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "logs" / "ocr_engine_comparison"),
        help="Directory for CSV/JSON/Markdown outputs",
    )
    parser.add_argument(
        "--parser-modes",
        default="regex",
        help="Comma separated parser modes to benchmark (e.g. regex,local_llm)",
    )
    parser.add_argument(
        "--skip-raw",
        action="store_true",
        help="Skip raw OCR text evaluation and only run parser modes",
    )
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise SystemExit(f"Labels file not found: {labels_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = parse_labels(labels_path)
    engines = [name.strip() for name in args.engines.split(",") if name.strip()]
    parser_modes = [name.strip() for name in args.parser_modes.split(",") if name.strip()]

    rows: list[dict[str, Any]] = []
    started_all = time.perf_counter()

    print(f"Parsed {len(labels)} labeled files with {sum(len(f.measurements) for f in labels)} labels")
    print(f"Engines: {', '.join(engines)}")

    for engine_name in engines:
        print(f"\n=== Engine: {engine_name} ===")
        try:
            engine = build_engine(engine_name)
        except Exception as exc:
            err = str(exc)
            print(f"  UNAVAILABLE: {err}")
            rows.append(
                {
                    "engine": engine_name,
                    "mode": "raw_no_parser",
                    "status": "unavailable",
                    "error": err,
                }
            )
            rows.append(
                {
                    "engine": engine_name,
                    "mode": _parser_label(parser_modes[0]) if parser_modes else "regex_parser",
                    "status": "unavailable",
                    "error": err,
                }
            )
            for parser_mode in parser_modes[1:]:
                rows.append(
                    {
                        "engine": engine_name,
                        "mode": _parser_label(parser_mode),
                        "status": "unavailable",
                        "error": err,
                    }
                )
            continue

        try:
            if not args.skip_raw:
                raw_scores = run_raw_text_eval(labels, engine)
                print(
                    "  raw_no_parser: "
                    f"box={format_rate(raw_scores.box_detect_rate)}, "
                    f"text={format_rate(raw_scores.text_detect_rate)}, "
                    f"full={format_rate(raw_scores.full_hit_rate)}"
                )
                rows.append(
                    {
                        "engine": engine_name,
                        "mode": "raw_no_parser",
                        "status": "ok",
                        "files": raw_scores.total_files,
                        "labels": raw_scores.total_labels,
                        "files_with_box": raw_scores.files_with_box,
                        "files_with_text": raw_scores.files_with_text,
                        "box_detect_rate": raw_scores.box_detect_rate,
                        "text_detect_rate": raw_scores.text_detect_rate,
                        "value_match_rate": raw_scores.value_hit_rate,
                        "name_match_rate": raw_scores.name_value_hit_rate,
                        "full_match_rate": raw_scores.full_hit_rate,
                        "predictions": "",
                        "elapsed_s": raw_scores.elapsed_s,
                        "error": "",
                    }
                )

            for parser_mode in parser_modes:
                parser_scores = run_evaluation(labels, engine, verbose=False, args=_Args(parser_mode))
                parser_label = _parser_label(parser_mode)
                print(
                    f"  {parser_label}: "
                    f"det={format_rate(parser_scores['detection_rate'])}, "
                    f"full={format_rate(parser_scores['full_match_rate'])}, "
                    f"value={format_rate(parser_scores['value_match_rate'])}"
                )
                rows.append(
                    {
                        "engine": engine_name,
                        "mode": parser_label,
                        "status": "ok",
                        "files": int(parser_scores["total_files"]),
                        "labels": int(parser_scores["total_labels"]),
                        "files_with_box": "",
                        "files_with_text": int(parser_scores["total_files_with_detections"]),
                        "box_detect_rate": "",
                        "text_detect_rate": parser_scores["detection_rate"],
                        "value_match_rate": parser_scores["value_match_rate"],
                        "name_match_rate": parser_scores["name_match_rate"],
                        "full_match_rate": parser_scores["full_match_rate"],
                        "predictions": int(parser_scores["total_predicted"]),
                        "elapsed_s": parser_scores["elapsed_s"],
                        "error": "",
                    }
                )
        except Exception as exc:
            err = str(exc)
            print(f"  FAILED: {err}")
            rows.append(
                {
                    "engine": engine_name,
                    "mode": "raw_no_parser",
                    "status": "failed",
                    "error": err,
                }
            )
            rows.append(
                {
                    "engine": engine_name,
                    "mode": _parser_label(parser_modes[0]) if parser_modes else "regex_parser",
                    "status": "failed",
                    "error": err,
                }
            )
            for parser_mode in parser_modes[1:]:
                rows.append(
                    {
                        "engine": engine_name,
                        "mode": _parser_label(parser_mode),
                        "status": "failed",
                        "error": err,
                    }
                )
        finally:
            stop_worker = getattr(engine, "_stop_worker", None)
            if callable(stop_worker):
                stop_worker()

    total_elapsed = time.perf_counter() - started_all

    csv_path = output_dir / "ocr_engine_matrix.csv"
    json_path = output_dir / "ocr_engine_matrix.json"
    md_path = output_dir / "ocr_engine_matrix.md"

    fieldnames = [
        "engine",
        "mode",
        "status",
        "files",
        "labels",
        "files_with_box",
        "files_with_text",
        "box_detect_rate",
        "text_detect_rate",
        "value_match_rate",
        "name_match_rate",
        "full_match_rate",
        "predictions",
        "elapsed_s",
        "error",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            complete = {key: row.get(key, "") for key in fieldnames}
            writer.writerow(complete)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump({"rows": rows, "elapsed_s": total_elapsed}, f, indent=2)

    ok_raw = [r for r in rows if r.get("mode") == "raw_no_parser" and r.get("status") == "ok"]
    ok_parser_rows = [
        r
        for r in rows
        if r.get("mode") != "raw_no_parser" and r.get("status") == "ok"
    ]
    parser_titles = {
        "regex": "Regex Parser",
        "local_llm": "Local LLM Parser (Qwen 2.5)",
    }

    md_lines = ["# OCR Engine Comparison", "", f"Total runtime: {total_elapsed:.1f}s"]

    if ok_raw:
        md_lines.extend(
            [
                "",
                "## Without Parser (raw OCR text)",
                "",
                "| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in ok_raw:
            md_lines.append(
                "| "
                f"{row['engine']} | {row['files']} | {format_rate(float(row['box_detect_rate']))} | "
                f"{format_rate(float(row['text_detect_rate']))} | {format_rate(float(row['value_match_rate']))} | "
                f"{format_rate(float(row['name_match_rate']))} | {format_rate(float(row['full_match_rate']))} | "
                f"{float(row['elapsed_s']):.1f} |"
            )

    for parser_mode in parser_modes:
        parser_label = _parser_label(parser_mode)
        parser_title = parser_titles.get(parser_mode, parser_label)
        parser_rows = [r for r in ok_parser_rows if r.get("mode") == parser_label]
        if not parser_rows:
            continue
        md_lines.extend(
            [
                "",
                f"## With {parser_title}",
                "",
                "| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in parser_rows:
            md_lines.append(
                "| "
                f"{row['engine']} | {row['files']} | {row['files_with_text']} | "
                f"{format_rate(float(row['full_match_rate']))} | {format_rate(float(row['value_match_rate']))} | "
                f"{format_rate(float(row['name_match_rate']))} | {row['predictions']} | {float(row['elapsed_s']):.1f} |"
            )

    failed_rows = [r for r in rows if r.get("status") in {"unavailable", "failed"}]
    if failed_rows:
        md_lines.extend(["", "## Engine Errors", ""])
        for row in failed_rows:
            md_lines.append(f"- {row.get('engine')} ({row.get('mode')}): {row.get('error', '')}")

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("\nSaved outputs:")
    print(f"  - {csv_path}")
    print(f"  - {json_path}")
    print(f"  - {md_path}")


if __name__ == "__main__":
    main()
