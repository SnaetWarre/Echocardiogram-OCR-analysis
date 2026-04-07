from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import multiprocessing as mp
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.types import PipelineRequest
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.runtime.startup_services import ServiceProcessManager

DEFAULT_OUTPUT_BASE = Path("artifacts/ocr_redesign/headless_batch_results")
DEFAULT_PATTERN = "*.dcm"
_worker_pipeline: EchoOcrPipeline | None = None
_worker_pipeline_key: tuple[tuple[str, Any], ...] | None = None


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
        "--workers",
        type=int,
        default=1,
        help="Number of isolated worker processes to use (default: 1).",
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


def _load_checkpoint(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    if not path.exists():
        return [], set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], set()

    items_raw = payload.get("items", [])
    if not isinstance(items_raw, list):
        return [], set()
    normalized: list[dict[str, Any]] = []
    for item in cast(list[Any], items_raw):
        if isinstance(item, dict):
            normalized.append(cast(dict[str, Any], item))
    processed = {
        str(item.get("dicom_path", "")).strip()
        for item in normalized
        if str(item.get("dicom_path", "")).strip()
    }
    return normalized, processed


def _normalize_line_predictions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(cast(list[Any], raw), start=1):
        if not isinstance(entry, dict):
            continue
        entry_obj = cast(dict[str, Any], entry)
        text = str(entry_obj.get("text", "")).strip()
        if not text:
            continue
        normalized.append(
            {
                "order": index,
                "text": text,
            }
        )
    return normalized


def _dataset_ids_for_path(input_root: Path, dicom_path: Path) -> tuple[str, str]:
    resolved_input = input_root.expanduser().resolve()
    resolved_dicom = dicom_path.expanduser().resolve()

    if resolved_input.is_dir():
        try:
            relative = resolved_dicom.relative_to(resolved_input)
            parts = relative.parts
            if len(parts) >= 3:
                return str(parts[0]), str(parts[1])
            if len(parts) == 2:
                return str(parts[0]), str(parts[0])
        except ValueError:
            pass

    parents = resolved_dicom.parents
    exam_id = parents[0].name if len(parents) >= 1 else ""
    patient_id = parents[1].name if len(parents) >= 2 else exam_id
    return patient_id, exam_id


def _sorted_prediction_rows(patients: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _patient_key, patient_entry in sorted(patients.items(), key=lambda pair: pair[0]):
        exams_map = cast(dict[str, dict[str, Any]], patient_entry["exams"])
        exam_rows: list[dict[str, Any]] = []
        for _exam_key, exam_entry in sorted(exams_map.items(), key=lambda pair: pair[0]):
            exam_rows.append(
                {
                    "exam_id": exam_entry["exam_id"],
                    "dicoms": exam_entry["dicoms"],
                }
            )
        rows.append(
            {
                "patient_id": patient_entry["patient_id"],
                "exams": exam_rows,
            }
        )
    return rows


def _build_nested_predictions(input_root: Path, items: list[dict[str, Any]]) -> dict[str, Any]:
    patients: dict[str, dict[str, Any]] = {}

    sorted_items = sorted(
        items,
        key=lambda item: (
            str(item.get("dicom_path", "")).strip(),
            str(item.get("status", "")).strip(),
        ),
    )

    for item in sorted_items:
        dicom_path_raw = str(item.get("dicom_path", "")).strip()
        if not dicom_path_raw:
            continue
        dicom_path = Path(dicom_path_raw)
        patient_id, exam_id = _dataset_ids_for_path(input_root, dicom_path)
        patient_key = patient_id or "__unknown_patient__"
        exam_key = exam_id or "__unknown_exam__"

        patient_entry = patients.setdefault(
            patient_key,
            {
                "patient_id": patient_id,
                "exams": {},
            },
        )
        exams_by_id = cast(dict[str, dict[str, Any]], patient_entry["exams"])
        exam_entry = exams_by_id.setdefault(
            exam_key,
            {
                "exam_id": exam_id,
                "dicoms": [],
            },
        )
        dicoms = cast(list[dict[str, Any]], exam_entry["dicoms"])
        dicoms.append(
            {
                "file_name": dicom_path.name,
                "file_path": _canonical_path(dicom_path),
                "measurements": _normalize_line_predictions(item.get("line_predictions", [])),
            }
        )

    return {"predictions": _sorted_prediction_rows(patients)}


def _scoped_resume_state(
    source_items: list[dict[str, Any]],
    source_processed: set[str],
    discovered_keys: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Keep only checkpoint/JSON rows whose DICOM path is in the current discovery set."""
    scoped_items = [
        item
        for item in source_items
        if str(item.get("dicom_path", "")).strip() in discovered_keys
    ]
    scoped_keys = {key for key in source_processed if key in discovered_keys}
    return scoped_items, scoped_keys


def _error_result_item(path: Path, exc: BaseException) -> dict[str, Any]:
    return {
        "dicom_path": _canonical_path(path),
        "status": "error",
        "measurements": [],
        "line_predictions": [],
        "metadata": {},
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


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
    predictions_raw = payload.get("predictions", [])
    if not isinstance(predictions_raw, list):
        return [], set()

    normalized: list[dict[str, Any]] = []
    for patient in cast(list[Any], predictions_raw):
        if not isinstance(patient, dict):
            continue
        patient_obj = cast(dict[str, Any], patient)
        exams = patient_obj.get("exams", [])
        if not isinstance(exams, list):
            continue
        for exam in cast(list[Any], exams):
            if not isinstance(exam, dict):
                continue
            exam_obj = cast(dict[str, Any], exam)
            dicoms = exam_obj.get("dicoms", [])
            if not isinstance(dicoms, list):
                continue
            for dicom in cast(list[Any], dicoms):
                if not isinstance(dicom, dict):
                    continue
                dicom_obj = cast(dict[str, Any], dicom)
                file_path = str(dicom_obj.get("file_path", "")).strip()
                if not file_path:
                    continue
                normalized.append(
                    {
                        "dicom_path": _canonical_path(Path(file_path)),
                        "status": "ok",
                        "measurements": [],
                        "line_predictions": _normalize_line_predictions(dicom_obj.get("measurements", [])),
                        "metadata": {},
                        "error": None,
                    }
                )

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

    for measurement in cast(list[Any], measurements):
        if not isinstance(measurement, dict):
            continue
        measurement_obj = cast(dict[str, Any], measurement)
        rows.append(
            {
                "dicom_path": str(item.get("dicom_path", "")),
                "status": str(item.get("status", "")),
                "measurement_name": str(measurement_obj.get("name", "")),
                "measurement_value": str(measurement_obj.get("value", "")),
                "measurement_unit": str(measurement_obj.get("unit", "") or ""),
                "measurement_source": str(measurement_obj.get("source", "") or ""),
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


def _worker_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "engine": str(args.engine),
        "fallback_engine": str(args.fallback_engine),
        "strict_engine_selection": bool(args.strict_engine_selection),
        "parser_mode": str(args.parser_mode),
        "max_frames": int(args.max_frames),
    }


def _build_pipeline_from_worker_config(config: dict[str, Any]) -> EchoOcrPipeline:
    return _build_pipeline(
        argparse.Namespace(
            engine=str(config.get("engine", "glm-ocr")),
            fallback_engine=str(config.get("fallback_engine", "surya")),
            strict_engine_selection=bool(config.get("strict_engine_selection", False)),
            parser_mode=str(config.get("parser_mode", "off")),
            max_frames=int(config.get("max_frames", 0)),
        )
    )


def _run_single_dicom_worker(config: dict[str, Any], dicom_path: str) -> dict[str, Any]:
    global _worker_pipeline, _worker_pipeline_key

    config_key = tuple(sorted(config.items(), key=lambda item: item[0]))
    if _worker_pipeline is None or _worker_pipeline_key != config_key:
        _worker_pipeline = _build_pipeline_from_worker_config(config)
        _worker_pipeline_key = config_key

    path = Path(dicom_path)
    try:
        result = _worker_pipeline.run(
            PipelineRequest(
                dicom_path=path,
                parameters={"max_frames": int(config.get("max_frames", 0))},
            )
        )
        return _result_to_item(path, result)
    except Exception as exc:
        return _error_result_item(path, exc)


def _process_pending_serial(
    pending: list[Path],
    *,
    args: argparse.Namespace,
    skipped: int,
    total: int,
    started_ts: float,
    items: list[dict[str, Any]],
    ok_count: int,
    error_count: int,
    checkpoint_path: Path,
) -> tuple[int, int]:
    pipeline = _build_pipeline(args)

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
            items.append(_error_result_item(path, exc))
            error_count += 1
            if not args.continue_on_error:
                break

        processed = skipped + index
        _print_progress(processed, total, started_ts, ok_count, error_count)

        if args.checkpoint_interval > 0 and processed % args.checkpoint_interval == 0:
            _save_checkpoint(checkpoint_path, items)

    return ok_count, error_count


def _process_pending_parallel(
    pending: list[Path],
    *,
    args: argparse.Namespace,
    skipped: int,
    total: int,
    started_ts: float,
    items: list[dict[str, Any]],
    ok_count: int,
    error_count: int,
    checkpoint_path: Path,
) -> tuple[int, int]:
    worker_count = max(1, int(args.workers))
    worker_config = _worker_config_from_args(args)
    pending_iter = iter(pending)
    completed = skipped
    executor = concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=mp.get_context("spawn"),
    )

    try:
        in_flight: dict[concurrent.futures.Future[dict[str, Any]], Path] = {}

        def submit_next() -> bool:
            try:
                next_path = next(pending_iter)
            except StopIteration:
                return False
            future = executor.submit(_run_single_dicom_worker, worker_config, _canonical_path(next_path))
            in_flight[future] = next_path
            return True

        initial_submit = min(worker_count, len(pending))
        for _ in range(initial_submit):
            if not submit_next():
                break

        stop_after_current_batch = False
        while in_flight:
            done, _ = concurrent.futures.wait(
                in_flight.keys(),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                path = in_flight.pop(future)
                try:
                    item = future.result()
                except Exception as exc:
                    item = _error_result_item(path, exc)

                items.append(item)
                if item.get("status") == "ok":
                    ok_count += 1
                else:
                    error_count += 1
                    if not args.continue_on_error:
                        stop_after_current_batch = True

                completed += 1
                _print_progress(completed, total, started_ts, ok_count, error_count)

                if args.checkpoint_interval > 0 and completed % args.checkpoint_interval == 0:
                    _save_checkpoint(checkpoint_path, items)

                if not stop_after_current_batch:
                    submit_next()

            if stop_after_current_batch:
                for future in in_flight:
                    future.cancel()
                break
    finally:
        executor.shutdown(wait=not bool(args.continue_on_error), cancel_futures=True)

    return ok_count, error_count


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
            "line_predictions": [],
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

    raw = cast(dict[str, Any], ai_result.raw) if isinstance(ai_result.raw, dict) else {}
    line_predictions = _normalize_line_predictions(raw.get("line_predictions", []))

    return {
        "dicom_path": _canonical_path(path),
        "status": "ok",
        "measurements": measurements,
        "line_predictions": line_predictions,
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

    discovered_keys = {_canonical_path(path) for path in discovered}
    items: list[dict[str, Any]] = []
    processed_keys: set[str] = set()

    if args.resume:
        checkpoint_items, checkpoint_processed = _load_checkpoint(output_paths.checkpoint_path)
        items, processed_keys = _scoped_resume_state(
            checkpoint_items, checkpoint_processed, discovered_keys
        )
        json_items, json_processed = _try_resume_from_json(output_paths.json_path)
        if json_items and len(json_items) > len(items):
            items, processed_keys = _scoped_resume_state(json_items, json_processed, discovered_keys)

    pending = [path for path in discovered if _canonical_path(path) not in processed_keys]
    total = len(discovered)
    skipped = total - len(pending)
    worker_count = max(1, int(args.workers))

    print(f"Discovered files: {total}")
    if skipped > 0:
        print(f"Skipped due to resume: {skipped}")
    print(f"Workers: {worker_count}")

    ok_count = sum(1 for item in items if item.get("status") == "ok")
    error_count = sum(1 for item in items if item.get("status") == "error")

    if worker_count == 1:
        ok_count, error_count = _process_pending_serial(
            pending,
            args=args,
            skipped=skipped,
            total=total,
            started_ts=started_ts,
            items=items,
            ok_count=ok_count,
            error_count=error_count,
            checkpoint_path=output_paths.checkpoint_path,
        )
    else:
        ok_count, error_count = _process_pending_parallel(
            pending,
            args=args,
            skipped=skipped,
            total=total,
            started_ts=started_ts,
            items=items,
            ok_count=ok_count,
            error_count=error_count,
            checkpoint_path=output_paths.checkpoint_path,
        )

    elapsed_s = round(time.perf_counter() - started_ts, 3)
    summary = {
        "total_discovered": total,
        "processed": len(items),
        "ok": ok_count,
        "error": error_count,
        "skipped": skipped,
    }
    payload = _build_nested_predictions(input_path, items)

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
