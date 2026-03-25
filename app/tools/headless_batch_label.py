from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.types import PipelineRequest
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.runtime.startup_services import ServiceProcessManager

DEFAULT_OUTPUT_BASE = Path("artifacts/ocr_redesign/headless_batch_results")
DEFAULT_PATTERN = "*.dcm"


@dataclass
class OutputPaths:
    json_path: Path | None
    csv_path: Path | None
    checkpoint_path: Path


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Headless batch DICOM labeling with Echo OCR pipeline. "
            "Writes aggregate JSON by default with optional CSV export."
        )
    )
    parser.add_argument("input_path", type=Path, help="Input DICOM file or directory.")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="Glob pattern for file discovery.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Use recursive discovery for directory input.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Maximum files to process (0 means all discovered files).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help="Base output path. Extension is inferred from --output-format.",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "csv", "both"),
        default="json",
        help="Output format mode.",
    )
    parser.add_argument(
        "--engine",
        default="glm-ocr",
        help="Primary OCR engine name.",
    )
    parser.add_argument(
        "--fallback-engine",
        default="surya",
        help="Fallback OCR engine name.",
    )
    parser.add_argument(
        "--strict-engine-selection",
        action="store_true",
        help="Fail if selected engine is not available instead of auto-fallback chain.",
    )
    parser.add_argument(
        "--parser-mode",
        default="off",
        help="Parser mode passthrough to EchoOcrPipeline.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Maximum frame count per DICOM (0 means all frames).",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue processing when a file fails (default: enabled).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint/output and skip already processed files.",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=None,
        help="Optional explicit checkpoint file path.",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=25,
        help="Write checkpoint every N processed files.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run startup checks and exit without processing input files.",
    )
    parser.add_argument("--run-id", default="", help="Optional run identifier.")
    parser.add_argument("--run-tag", default="", help="Optional run tag.")
    parser.add_argument("--run-note", default="", help="Optional run note.")
    return parser


def discover_files(root: Path, pattern: str, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.match(pattern) else []

    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    files = [path for path in iterator if path.is_file()]
    return sorted(files, key=lambda p: _canonical_path(p))


def _resolve_output_paths(
    output_base: Path,
    output_format: str,
    checkpoint_override: Path | None,
) -> OutputPaths:
    base = output_base.expanduser()
    if base.is_dir():
        base = base / "headless_batch_results"

    json_path: Path | None = None
    csv_path: Path | None = None

    if output_format in {"json", "both"}:
        json_path = base if base.suffix.lower() == ".json" else base.with_suffix(".json")
    if output_format in {"csv", "both"}:
        csv_path = base if base.suffix.lower() == ".csv" else base.with_suffix(".csv")

    checkpoint_path = (
        checkpoint_override.expanduser()
        if checkpoint_override is not None
        else (base.with_suffix(".checkpoint.json"))
    )
    return OutputPaths(json_path=json_path, csv_path=csv_path, checkpoint_path=checkpoint_path)


def _safe_read_mem_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                parts = line.split()
                if len(parts) < 2:
                    return None
                kb = float(parts[1])
                return round(kb / 1024 / 1024, 2)
    except Exception:
        return None
    return None


def _detect_gpu() -> bool:
    # Lightweight check only for startup observability.
    return any(Path(binary).exists() for binary in ("/usr/bin/nvidia-smi", "/bin/nvidia-smi"))


def _resource_snapshot() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "cpu_count": os.cpu_count() or 0,
        "ram_gb": _safe_read_mem_gb(),
        "gpu_detected": _detect_gpu(),
    }


def _load_checkpoint(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    if not path.exists():
        return [], set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], set()

    items = payload.get("items", [])
    if not isinstance(items, list):
        return [], set()
    normalized = [item for item in items if isinstance(item, dict)]
    processed = {
        str(item.get("dicom_path", "")).strip()
        for item in normalized
        if str(item.get("dicom_path", "")).strip()
    }
    return normalized, processed


def _save_checkpoint(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": _iso_now(),
        "items": items,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _try_resume_from_json(path: Path | None) -> tuple[list[dict[str, Any]], set[str]]:
    if path is None or not path.exists():
        return [], set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], set()
    items = payload.get("items", [])
    if not isinstance(items, list):
        return [], set()
    normalized = [item for item in items if isinstance(item, dict)]
    processed = {
        str(item.get("dicom_path", "")).strip()
        for item in normalized
        if str(item.get("dicom_path", "")).strip()
    }
    return normalized, processed


def _measurement_rows(item: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    measurements = item.get("measurements", [])
    if not isinstance(measurements, list):
        measurements = []
    if not measurements:
        rows.append(
            {
                "dicom_path": str(item.get("dicom_path", "")),
                "status": str(item.get("status", "")),
                "measurement_name": "",
                "measurement_value": "",
                "measurement_unit": "",
                "measurement_source": "",
                "error": str(item.get("error", {}).get("message", ""))
                if isinstance(item.get("error", {}), dict)
                else "",
            }
        )
        return rows

    for measurement in measurements:
        if not isinstance(measurement, dict):
            continue
        rows.append(
            {
                "dicom_path": str(item.get("dicom_path", "")),
                "status": str(item.get("status", "")),
                "measurement_name": str(measurement.get("name", "")),
                "measurement_value": str(measurement.get("value", "")),
                "measurement_unit": str(measurement.get("unit", "") or ""),
                "measurement_source": str(measurement.get("source", "") or ""),
                "error": "",
            }
        )
    return rows


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dicom_path",
        "status",
        "measurement_name",
        "measurement_value",
        "measurement_unit",
        "measurement_source",
        "error",
    ]
    rows: list[dict[str, str]] = []
    for item in items:
        rows.extend(_measurement_rows(item))

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_pipeline(args: argparse.Namespace) -> EchoOcrPipeline:
    parameters: dict[str, Any] = {
        "ocr_engine": args.engine,
        "requested_ocr_engine": args.engine,
        "fallback_ocr_engine": args.fallback_engine,
        "strict_ocr_engine_selection": bool(args.strict_engine_selection),
        "parser_mode": args.parser_mode,
    }
    if args.max_frames > 0:
        parameters["max_frames"] = int(args.max_frames)

    config = PipelineConfig(parameters=parameters)
    pipeline = EchoOcrPipeline(config=config)
    pipeline.ensure_components()
    return pipeline


def run_preflight(engine: str, fallback_engine: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def _run_check(name: str, action: Callable[[], object]) -> None:
        started = time.perf_counter()
        status = "ok"
        error = ""
        try:
            action()
        except Exception as exc:
            status = "error"
            error = str(exc)
        checks.append(
            {
                "name": name,
                "status": status,
                "error": error,
                "elapsed_s": round(time.perf_counter() - started, 3),
            }
        )

    if engine == "glm-ocr" or fallback_engine == "glm-ocr":
        _run_check("glm_ocr_worker", ServiceProcessManager._ensure_glm_ocr_worker)
    if engine == "surya" or fallback_engine == "surya":
        _run_check("surya_worker", ServiceProcessManager._ensure_surya_worker)

    if engine not in {"glm-ocr", "surya"}:
        _run_check(f"engine_{engine}", lambda: _build_pipeline(argparse.Namespace(
            engine=engine,
            fallback_engine=fallback_engine,
            strict_engine_selection=True,
            parser_mode="off",
            max_frames=0,
        )))

    return {
        "checked_at": _iso_now(),
        "engine": engine,
        "fallback_engine": fallback_engine,
        "checks": checks,
        "ok": all(check["status"] == "ok" for check in checks),
    }


def _result_to_item(path: Path, result: Any) -> dict[str, Any]:
    if getattr(result, "status", "") != "ok" or getattr(result, "ai_result", None) is None:
        return {
            "dicom_path": _canonical_path(path),
            "status": "error",
            "measurements": [],
            "metadata": {},
            "error": {
                "type": "PipelineError",
                "message": str(getattr(result, "error", "unknown error")),
            },
        }

    ai_result = result.ai_result
    measurements: list[dict[str, Any]] = []
    for measurement in ai_result.measurements:
        measurements.append(
            {
                "name": measurement.name,
                "value": measurement.value,
                "unit": measurement.unit,
                "source": measurement.source,
            }
        )

    raw = ai_result.raw if isinstance(ai_result.raw, dict) else {}
    line_predictions = raw.get("line_predictions", [])
    if not isinstance(line_predictions, list):
        line_predictions = []

    return {
        "dicom_path": _canonical_path(path),
        "status": "ok",
        "measurements": measurements,
        "metadata": {
            "model_name": ai_result.model_name,
            "created_at": ai_result.created_at.isoformat(),
            "record_count": raw.get("record_count", 0),
            "source_kinds": raw.get("source_kinds", []),
            "parser_sources": raw.get("parser_sources", []),
            "line_prediction_count": len(line_predictions),
            "ocr_benchmark": raw.get("ocr_benchmark", {}),
        },
        "error": None,
    }


def _print_progress(processed: int, total: int, started_at: float, ok_count: int, error_count: int) -> None:
    elapsed = max(time.perf_counter() - started_at, 1e-6)
    throughput = processed / elapsed
    remaining = max(total - processed, 0)
    eta_s = remaining / throughput if throughput > 0 else 0.0
    print(
        f"[{processed}/{total}] ok={ok_count} error={error_count} "
        f"rate={throughput:.2f}/s eta={eta_s:.1f}s"
    )


def run_batch(args: argparse.Namespace) -> int:
    started_ts = time.perf_counter()
    started_at = _iso_now()
    output_paths = _resolve_output_paths(args.output, args.output_format, args.checkpoint_path)

    if args.preflight:
        report = run_preflight(engine=args.engine, fallback_engine=args.fallback_engine)
        if output_paths.json_path is not None:
            write_json(output_paths.json_path, report)
            print(f"Preflight report written: {output_paths.json_path}")
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("ok", False) else 1

    input_path = args.input_path.expanduser()
    if not input_path.exists():
        print(f"Input path not found: {input_path}")
        return 2

    discovered = discover_files(input_path, args.pattern, args.recursive)
    if args.max_files > 0:
        discovered = discovered[: args.max_files]
    if not discovered:
        print("No matching files found.")
        return 1

    items: list[dict[str, Any]] = []
    processed_keys: set[str] = set()

    if args.resume:
        checkpoint_items, checkpoint_processed = _load_checkpoint(output_paths.checkpoint_path)
        items.extend(checkpoint_items)
        processed_keys |= checkpoint_processed
        json_items, json_processed = _try_resume_from_json(output_paths.json_path)
        if json_items and len(json_items) > len(items):
            items = json_items
            processed_keys = json_processed

    pending = [path for path in discovered if _canonical_path(path) not in processed_keys]
    total = len(discovered)
    skipped = total - len(pending)

    print(f"Discovered files: {total}")
    if skipped > 0:
        print(f"Skipped due to resume: {skipped}")

    pipeline = _build_pipeline(args)

    ok_count = sum(1 for item in items if item.get("status") == "ok")
    error_count = sum(1 for item in items if item.get("status") == "error")

    for index, path in enumerate(pending, start=1):
        try:
            result = pipeline.run(PipelineRequest(dicom_path=path, parameters={"max_frames": args.max_frames}))
            item = _result_to_item(path, result)
            items.append(item)
            if item.get("status") == "ok":
                ok_count += 1
            else:
                error_count += 1
                if not args.continue_on_error:
                    raise RuntimeError(str(item.get("error", {}).get("message", "pipeline error")))
        except Exception as exc:
            item = {
                "dicom_path": _canonical_path(path),
                "status": "error",
                "measurements": [],
                "metadata": {},
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }
            items.append(item)
            error_count += 1
            if not args.continue_on_error:
                break

        processed = skipped + index
        _print_progress(processed, total, started_ts, ok_count, error_count)

        if args.checkpoint_interval > 0 and processed % args.checkpoint_interval == 0:
            _save_checkpoint(output_paths.checkpoint_path, items)

    ended_at = _iso_now()
    elapsed_s = round(time.perf_counter() - started_ts, 3)
    summary = {
        "total_discovered": total,
        "processed": len(items),
        "ok": ok_count,
        "error": error_count,
        "skipped": skipped,
    }
    payload = {
        "manifest": {
            "run_id": args.run_id.strip() or f"headless-{int(time.time())}",
            "run_tag": args.run_tag.strip(),
            "run_note": args.run_note.strip(),
            "started_at": started_at,
            "ended_at": ended_at,
            "elapsed_s": elapsed_s,
            "args": {
                "input_path": str(input_path),
                "pattern": args.pattern,
                "recursive": bool(args.recursive),
                "max_files": int(args.max_files),
                "output_format": args.output_format,
                "engine": args.engine,
                "fallback_engine": args.fallback_engine,
                "strict_engine_selection": bool(args.strict_engine_selection),
                "parser_mode": args.parser_mode,
                "max_frames": int(args.max_frames),
                "continue_on_error": bool(args.continue_on_error),
                "resume": bool(args.resume),
            },
            "resources": _resource_snapshot(),
            "summary": summary,
        },
        "items": items,
    }

    if output_paths.json_path is not None:
        write_json(output_paths.json_path, payload)
        print(f"JSON written: {output_paths.json_path}")
    if output_paths.csv_path is not None:
        write_csv(output_paths.csv_path, items)
        print(f"CSV written: {output_paths.csv_path}")

    _save_checkpoint(output_paths.checkpoint_path, items)
    print(f"Checkpoint written: {output_paths.checkpoint_path}")

    print("Summary")
    print("-------")
    print(f"Discovered: {summary['total_discovered']}")
    print(f"Processed:  {summary['processed']}")
    print(f"OK:         {summary['ok']}")
    print(f"Error:      {summary['error']}")
    print(f"Skipped:    {summary['skipped']}")
    print(f"Elapsed:    {elapsed_s:.2f}s")

    if error_count > 0 and not args.continue_on_error:
        return 1
    return 0 if error_count == 0 or args.continue_on_error else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_batch(args)


if __name__ == "__main__":
    raise SystemExit(main())
