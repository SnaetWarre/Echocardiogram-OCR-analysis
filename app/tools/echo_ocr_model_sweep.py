from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_MODELS = [
    "qwen2.5:7b-instruct-q4_K_M",
    "qwen2.5:7b-instruct-q5_K_M",
    "qwen3:4b",
    "qwen3:8b",
    "nuextract:latest",
]

DEFAULT_PARSER_MODES = ["hybrid"]


@dataclass(frozen=True)
class EvalSummary:
    model: str
    parser_mode: str
    out_file: Path
    precision: float
    recall: float
    precision_relaxed: float
    recall_relaxed: float
    strict_f1: float
    relaxed_f1: float


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())


def _extract_metric(report: str, label: str) -> float:
    match = re.search(rf"^{re.escape(label)}:\s*([0-9]+(?:\.[0-9]+)?)\s*$", report, re.MULTILINE)
    if not match:
        raise ValueError(f"Metric '{label}' not found in report.")
    return float(match.group(1))


def _f1(precision: float, recall: float) -> float:
    if precision <= 0.0 and recall <= 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _run_eval_once(
    *,
    labels: Path,
    out_file: Path,
    model: str,
    parser_mode: str,
    ocr_engine: str,
    xdg_cache_home: Path,
) -> EvalSummary:
    env = os.environ.copy()
    env["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    env["ECHO_OCR_ENGINE"] = ocr_engine
    env["ECHO_PARSER_MODE"] = parser_mode
    env["ECHO_LLM_MODEL"] = model
    env["XDG_CACHE_HOME"] = str(xdg_cache_home)

    cmd = [
        sys.executable,
        "-m",
        "app.tools.echo_ocr_eval_labels",
        "--labels",
        str(labels),
        "--out",
        str(out_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Eval failed for model={model}, parser={parser_mode}: {msg}")

    report = out_file.read_text(encoding="utf-8")
    precision = _extract_metric(report, "Precision")
    recall = _extract_metric(report, "Recall")
    precision_relaxed = _extract_metric(report, "Relaxed precision")
    recall_relaxed = _extract_metric(report, "Relaxed recall")
    return EvalSummary(
        model=model,
        parser_mode=parser_mode,
        out_file=out_file,
        precision=precision,
        recall=recall,
        precision_relaxed=precision_relaxed,
        recall_relaxed=recall_relaxed,
        strict_f1=_f1(precision, recall),
        relaxed_f1=_f1(precision_relaxed, recall_relaxed),
    )


def _print_summary(items: Sequence[EvalSummary]) -> None:
    ranked = sorted(
        items,
        key=lambda x: (x.relaxed_f1, x.strict_f1, x.precision_relaxed, x.recall_relaxed),
        reverse=True,
    )
    print("")
    print("Echo OCR Model Sweep Ranking")
    print("============================")
    print(
        "rank | model                          | parser   | strict(P/R/F1)        "
        "| relaxed(P/R/F1)       | report"
    )
    print(
        "-----+--------------------------------+----------+-----------------------"
        "-+----------------------+------------------------------"
    )
    for idx, row in enumerate(ranked, start=1):
        strict = f"{row.precision:.4f}/{row.recall:.4f}/{row.strict_f1:.4f}"
        relaxed = f"{row.precision_relaxed:.4f}/{row.recall_relaxed:.4f}/{row.relaxed_f1:.4f}"
        print(
            f"{idx:>4} | {row.model[:30]:<30} | {row.parser_mode:<8} | "
            f"{strict:<21} | {relaxed:<20} | {row.out_file}"
        )
    best = ranked[0]
    print("")
    print(
        f"Best config: model={best.model}, parser={best.parser_mode}, "
        f"relaxed_f1={best.relaxed_f1:.4f}, strict_f1={best.strict_f1:.4f}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OCR labels eval across multiple local LLM models.")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("labels.md"),
        help="Path to labels markdown file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/model-sweep"),
        help="Directory to store per-run reports.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Model tags to test (space-separated).",
    )
    parser.add_argument(
        "--parser-modes",
        nargs="+",
        default=DEFAULT_PARSER_MODES,
        choices=["hybrid", "local_llm"],
        help="Parser mode(s) to test.",
    )
    parser.add_argument(
        "--ocr-engine",
        default="paddleocr",
        help="OCR engine name to use (default: paddleocr).",
    )
    parser.add_argument(
        "--xdg-cache-home",
        type=Path,
        default=Path(".cache"),
        help="Cache directory used by mamba/python runtime.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.labels.exists():
        print(f"labels file not found: {args.labels}")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.xdg_cache_home.mkdir(parents=True, exist_ok=True)

    results: List[EvalSummary] = []
    for parser_mode in args.parser_modes:
        for model in args.models:
            model_slug = _safe_slug(model)
            out_file = args.out_dir / f"eval_{parser_mode}_{model_slug}.md"
            print(f"[RUN] parser={parser_mode} model={model}")
            summary = _run_eval_once(
                labels=args.labels,
                out_file=out_file,
                model=model,
                parser_mode=parser_mode,
                ocr_engine=args.ocr_engine,
                xdg_cache_home=args.xdg_cache_home,
            )
            print(
                "[OK]  "
                f"strict={summary.precision:.4f}/{summary.recall:.4f} "
                f"relaxed={summary.precision_relaxed:.4f}/{summary.recall_relaxed:.4f}"
            )
            results.append(summary)

    _print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
