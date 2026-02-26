from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from app.models.types import PipelineRequest  # noqa: E402
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline  # noqa: E402


@dataclass(frozen=True)
class ExpectedMeasurement:
    name: str
    value: str
    unit: str


@dataclass(frozen=True)
class LabeledCase:
    path: Path
    measurements: List[ExpectedMeasurement]


MEASUREMENT_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>[^\s]+)?\s*$"
)


def _norm_space(value: str) -> str:
    return " ".join(value.strip().split())


def _norm_name(value: str) -> str:
    name = _norm_space(value)
    aliases = {
        "tr maxpg": "TR maxPG",
        "tr vmax": "TR Vmax",
        "pv maxpg": "PV maxPG",
        "pv vmax": "PV Vmax",
        "ef(teich)": "EF(Teich)",
        "ef (teich)": "EF(Teich)",
        "laesv(a-l)": "LAESV (A-L)",
        "laesv (a-l)": "LAESV (A-L)",
        "laesv a-l": "LAESV (A-L)",
        "ao diam": "Ao Diam",
        "ao asc": "Ao asc",
        "arch diam": "Ao arch diam",
        "lvsv": "SV",
        "lvot diam": "LVOT Diam",
        "la diam": "LA Diam",
    }
    lowered = name.lower()
    return aliases.get(lowered, name)


_VIEW_SUFFIXES = re.compile(
    r"\s*(?:a4c|a2c|a3c|mod|bp|a-l|\(a-l\))\s*", re.IGNORECASE
)


def _relaxed_name_key(value: str) -> str:
    lowered = _norm_name(value).lower().replace("¥", "v")
    # Strip view/method suffixes for relaxed matching (LAAS A4C ≈ LAAS)
    stripped = _VIEW_SUFFIXES.sub(" ", lowered)
    stripped = " ".join(stripped.split())
    return re.sub(r"[^a-z0-9]+", "", stripped)


def _norm_value(value: str) -> str:
    return value.replace(",", ".").strip()


def _norm_unit(value: str) -> str:
    unit = value.strip()
    if not unit:
        return ""
    lowered = unit.lower()
    aliases = {
        "mis": "m/s",
        "m1s": "m/s",
        "mls": "m/s",
        "mmhg": "mmHg",
        "cm2": "cm2",
        "m/s2": "m/s2",
        "ml/m2": "ml/m2",
    }
    if lowered in aliases:
        return aliases[lowered]
    return unit


def _parse_measurement_line(raw: str) -> ExpectedMeasurement | None:
    text = raw.strip()
    match = MEASUREMENT_RE.match(text)
    if not match:
        return None
    name = _norm_name(match.group("name"))
    value = _norm_value(match.group("value"))
    unit = _norm_unit(match.group("unit") or "")
    return ExpectedMeasurement(name=name, value=value, unit=unit)


def parse_labels_md(path: Path) -> List[LabeledCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cases: List[LabeledCase] = []
    current_path: Path | None = None
    current_measurements: List[ExpectedMeasurement] = []

    def flush() -> None:
        nonlocal current_path, current_measurements
        if current_path is not None:
            cases.append(LabeledCase(path=current_path, measurements=list(current_measurements)))
        current_path = None
        current_measurements = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("path:"):
            flush()
            raw_path = stripped.split("path:", 1)[1].strip()
            p = Path(raw_path)
            if p.suffix.lower() == ".documents":
                p = p.with_suffix(".dcm")
            current_path = p
            continue
        if stripped.startswith("->"):
            payload = stripped.split("->", 1)[1].strip()
            parsed = _parse_measurement_line(payload)
            if parsed is not None:
                current_measurements.append(parsed)
            continue
        if stripped.startswith("--"):
            flush()
            continue

    flush()
    return cases


def as_key(name: str, value: str, unit: str) -> str:
    return f"{_norm_name(name).lower()}|{_norm_value(value)}|{_norm_unit(unit).lower()}"


def as_relaxed_key(name: str, value: str, unit: str) -> str:
    return f"{_relaxed_name_key(name)}|{_norm_value(value)}|{_norm_unit(unit).lower()}"


def evaluate_cases(cases: Sequence[LabeledCase]) -> Dict[str, object]:
    pipeline = EchoOcrPipeline()
    missing_files: List[str] = []
    per_file: List[Dict[str, object]] = []
    expected_total = 0
    predicted_total = 0
    true_positive = 0
    true_positive_relaxed = 0

    for case in cases:
        if not case.path.exists():
            missing_files.append(str(case.path))
            continue
        result = pipeline.run(PipelineRequest(dicom_path=case.path))
        predicted = result.ai_result.measurements if result.ai_result is not None else []
        expected_keys: Set[str] = {as_key(m.name, m.value, m.unit) for m in case.measurements}
        predicted_keys: Set[str] = {
            as_key(m.name, m.value, m.unit or "") for m in predicted
        }
        expected_relaxed: Set[str] = {as_relaxed_key(m.name, m.value, m.unit) for m in case.measurements}
        predicted_relaxed: Set[str] = {
            as_relaxed_key(m.name, m.value, m.unit or "") for m in predicted
        }
        hit_keys = expected_keys & predicted_keys
        hit_relaxed_keys = expected_relaxed & predicted_relaxed
        miss_keys = sorted(expected_keys - predicted_keys)
        extra_keys = sorted(predicted_keys - expected_keys)

        expected_total += len(expected_keys)
        predicted_total += len(predicted_keys)
        true_positive += len(hit_keys)
        true_positive_relaxed += len(hit_relaxed_keys)

        per_file.append(
            {
                "path": str(case.path),
                "status": result.status,
                "expected": len(expected_keys),
                "predicted": len(predicted_keys),
                "hits": len(hit_keys),
                "misses": miss_keys,
                "extras": extra_keys,
            }
        )

    precision = (true_positive / predicted_total) if predicted_total else 0.0
    recall = (true_positive / expected_total) if expected_total else 0.0
    precision_relaxed = (true_positive_relaxed / predicted_total) if predicted_total else 0.0
    recall_relaxed = (true_positive_relaxed / expected_total) if expected_total else 0.0
    return {
        "cases_total": len(cases),
        "cases_evaluated": len(per_file),
        "missing_files": missing_files,
        "expected_total": expected_total,
        "predicted_total": predicted_total,
        "true_positive": true_positive,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "true_positive_relaxed": true_positive_relaxed,
        "precision_relaxed": round(precision_relaxed, 4),
        "recall_relaxed": round(recall_relaxed, 4),
        "per_file": per_file,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate OCR extraction quality on labels.md.")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("labels.md"),
        help="Path to labels markdown file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/ocr-eval/labels_eval.txt"),
        help="Path to write human-readable report.",
    )
    return parser.parse_args()


def format_report(stats: Dict[str, object]) -> str:
    lines = [
        "Echo OCR Labels Evaluation",
        "==========================",
        f"Cases total: {stats['cases_total']}",
        f"Cases evaluated: {stats['cases_evaluated']}",
        f"Missing files: {len(stats['missing_files'])}",
        f"Expected total measurements: {stats['expected_total']}",
        f"Predicted total measurements: {stats['predicted_total']}",
        f"True positives: {stats['true_positive']}",
        f"Precision: {stats['precision']}",
        f"Recall: {stats['recall']}",
        f"Relaxed true positives: {stats['true_positive_relaxed']}",
        f"Relaxed precision: {stats['precision_relaxed']}",
        f"Relaxed recall: {stats['recall_relaxed']}",
        "",
        "Per-file details:",
    ]
    for item in stats["per_file"]:
        lines.append(
            f"- {item['path']} | status={item['status']} expected={item['expected']} "
            f"predicted={item['predicted']} hits={item['hits']}"
        )
        misses = item["misses"]
        extras = item["extras"]
        if misses:
            lines.append(f"  misses: {', '.join(misses)}")
        if extras:
            lines.append(f"  extras: {', '.join(extras)}")
    if stats["missing_files"]:
        lines.append("")
        lines.append("Missing files:")
        for path in stats["missing_files"]:
            lines.append(f"- {path}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if not args.labels.exists():
        print(f"labels file not found: {args.labels}")
        return 2
    cases = parse_labels_md(args.labels)
    if not cases:
        print("no labeled cases found")
        return 1
    stats = evaluate_cases(cases)
    report = format_report(stats)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(report)
    print(f"saved report to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
