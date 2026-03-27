from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.types import PipelineRequest
from app.ocr.preprocessing import _to_gray
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.ocr_engines import build_engine
from app.validation.datasets import LabeledFile, parse_labels, parse_requested_splits
from app.validation.evaluation import score_predictions

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "ocr_redesign" / "preprocess_sweep"
DEFAULT_LABELS_PATH = PROJECT_ROOT / "labels" / "labels.json"


class PerFileTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class PreprocessSpec:
    contrast_mode: str = "none"
    scale_factor: int = 1
    scale_algo: str = "linear"
    unsharp: bool = False
    threshold_mode: str = "none"
    morph_close: bool = False
    smooth: bool = False


@dataclass(frozen=True)
class SweepConfig:
    name: str
    description: str
    default_view: PreprocessSpec
    multiview_mode: str = "none"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def _discover_files(root: Path, pattern: str, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.match(pattern) else []
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    files = [path for path in iterator if path.is_file()]
    return sorted(files, key=lambda p: _canonical_path(p))


def _preprocess_with_spec(image: np.ndarray, spec: PreprocessSpec) -> np.ndarray:
    gray = _to_gray(image)
    if gray.size == 0:
        return gray

    if spec.contrast_mode == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        working = clahe.apply(gray)
    elif spec.contrast_mode == "adaptive_threshold":
        working = cv2.equalizeHist(gray)
    else:
        working = gray

    if spec.unsharp:
        gaussian = cv2.GaussianBlur(working, (5, 5), 1.0)
        working = cv2.addWeighted(working, 1.5, gaussian, -0.5, 0)

    scale = max(1, min(int(spec.scale_factor), 6))
    if scale > 1:
        interpolation_map = {
            "linear": cv2.INTER_LINEAR,
            "cubic": cv2.INTER_CUBIC,
            "lanczos": cv2.INTER_LANCZOS4,
        }
        inter_flag = interpolation_map.get(str(spec.scale_algo).lower(), cv2.INTER_CUBIC)
        width = int(working.shape[1] * scale)
        height = int(working.shape[0] * scale)
        working = cv2.resize(working, (width, height), interpolation=inter_flag)

    if spec.threshold_mode == "adaptive":
        working = cv2.adaptiveThreshold(
            working,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
    elif spec.threshold_mode == "otsu":
        _ret, working = cv2.threshold(working, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if spec.morph_close and spec.threshold_mode != "none":
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        working = cv2.morphologyEx(working, cv2.MORPH_CLOSE, kernel)

    if spec.smooth and spec.threshold_mode != "none":
        blurred = cv2.GaussianBlur(working, (3, 3), 0.6)
        _ret, working = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

    return working


def _pipeline_alt_views(default_spec: PreprocessSpec) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    high_contrast = PreprocessSpec(
        contrast_mode="adaptive_threshold",
        scale_factor=default_spec.scale_factor,
        scale_algo=default_spec.scale_algo,
        unsharp=default_spec.unsharp,
        threshold_mode="adaptive",
        morph_close=True,
        smooth=False,
    )
    clahe = PreprocessSpec(
        contrast_mode="clahe",
        scale_factor=default_spec.scale_factor,
        scale_algo=default_spec.scale_algo,
        unsharp=default_spec.unsharp,
        threshold_mode="otsu",
        morph_close=True,
        smooth=False,
    )
    return {
        "high_contrast": lambda image, _spec=high_contrast: _preprocess_with_spec(image, _spec),
        "clahe": lambda image, _spec=clahe: _preprocess_with_spec(image, _spec),
    }


def _build_preprocess_views(config: SweepConfig) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    views: dict[str, Callable[[np.ndarray], np.ndarray]] = {
        "default": lambda image, _spec=config.default_view: _preprocess_with_spec(image, _spec)
    }
    if config.multiview_mode == "pipeline":
        views.update(_pipeline_alt_views(config.default_view))
    return views


def _smoke_configs() -> list[SweepConfig]:
    return [
        SweepConfig(
            name="no_preprocess_gray",
            description="Grayscale only, no upscale, no sharpening, no binarization, no multiview.",
            default_view=PreprocessSpec(),
        ),
        SweepConfig(
            name="default_single",
            description="Current step-6 style default only: unsharp, x3 Lanczos, Otsu, morph close.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_multiview",
            description="Current step-6 plus step-7 multiview retries (adaptive + clahe).",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
            multiview_mode="pipeline",
        ),
    ]


def _broad_configs() -> list[SweepConfig]:
    return [
        SweepConfig(
            name="no_preprocess_gray",
            description="Grayscale only, no upscale, no sharpening, no binarization, no multiview.",
            default_view=PreprocessSpec(),
        ),
        SweepConfig(
            name="gray_x2_cubic",
            description="Grayscale only with x2 cubic upscale.",
            default_view=PreprocessSpec(scale_factor=2, scale_algo="cubic"),
        ),
        SweepConfig(
            name="gray_x3_lanczos",
            description="Grayscale only with x3 Lanczos upscale.",
            default_view=PreprocessSpec(scale_factor=3, scale_algo="lanczos"),
        ),
        SweepConfig(
            name="unsharp_x3_lanczos",
            description="Grayscale + unsharp mask + x3 Lanczos, no binarization.",
            default_view=PreprocessSpec(scale_factor=3, scale_algo="lanczos", unsharp=True),
        ),
        SweepConfig(
            name="otsu_x3_lanczos_no_unsharp",
            description="Grayscale + x3 Lanczos + Otsu threshold, no unsharp, no morph close.",
            default_view=PreprocessSpec(
                scale_factor=3,
                scale_algo="lanczos",
                threshold_mode="otsu",
            ),
        ),
        SweepConfig(
            name="otsu_close_x3_lanczos_no_unsharp",
            description="Grayscale + x3 Lanczos + Otsu + morph close, no unsharp.",
            default_view=PreprocessSpec(
                scale_factor=3,
                scale_algo="lanczos",
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_single",
            description="Current step-6 style default only: unsharp, x3 Lanczos, Otsu, morph close.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_multiview",
            description="Current step-6 plus step-7 multiview retries (adaptive + clahe).",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
            multiview_mode="pipeline",
        ),
        SweepConfig(
            name="default_smooth_single",
            description="Current step-6 default with extra post-binary smoothing.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
                smooth=True,
            ),
        ),
        SweepConfig(
            name="default_x2_lanczos_single",
            description="Current default pipeline but x2 Lanczos instead of x3.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=2,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_x3_cubic_single",
            description="Current default pipeline but x3 cubic instead of Lanczos.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="cubic",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_x3_linear_single",
            description="Current default pipeline but x3 linear instead of Lanczos.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="linear",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="clahe_single",
            description="CLAHE + unsharp + x3 Lanczos + Otsu + morph close, no multiview.",
            default_view=PreprocessSpec(
                contrast_mode="clahe",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="adaptive_single",
            description="Equalize hist + unsharp + x3 Lanczos + adaptive threshold + morph close.",
            default_view=PreprocessSpec(
                contrast_mode="adaptive_threshold",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="adaptive",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="adaptive_smooth_single",
            description="Adaptive-threshold pipeline with extra post-binary smoothing.",
            default_view=PreprocessSpec(
                contrast_mode="adaptive_threshold",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="adaptive",
                morph_close=True,
                smooth=True,
            ),
        ),
    ]


def _select_configs(config_set: str) -> list[SweepConfig]:
    if config_set == "smoke":
        return _smoke_configs()
    if config_set == "broad":
        return _broad_configs()
    raise ValueError(f"Unsupported config set: {config_set}")


def _filter_configs(
    configs: list[SweepConfig],
    *,
    only_configs: str,
    exclude_configs: str,
) -> list[SweepConfig]:
    selected = configs
    if only_configs.strip():
        wanted = {item.strip() for item in only_configs.split(",") if item.strip()}
        selected = [config for config in selected if config.name in wanted]
    if exclude_configs.strip():
        blocked = {item.strip() for item in exclude_configs.split(",") if item.strip()}
        selected = [config for config in selected if config.name not in blocked]
    return selected


def _build_pipeline(engine_name: str, parser_mode: str, config: SweepConfig) -> EchoOcrPipeline:
    engine = build_engine(engine_name)
    pipeline = EchoOcrPipeline(
        ocr_engine=engine,
        config=PipelineConfig(
            parameters={
                "ocr_engine": engine_name,
                "requested_ocr_engine": engine_name,
                "parser_mode": parser_mode,
            }
        ),
    )
    pipeline._line_transcriber.preprocess_views = _build_preprocess_views(config)
    pipeline.ensure_components()
    return pipeline


def _result_to_item(path: Path, result: Any, config: SweepConfig) -> dict[str, Any]:
    if getattr(result, "status", "") != "ok" or getattr(result, "ai_result", None) is None:
        return {
            "dicom_path": _canonical_path(path),
            "status": "error",
            "measurements": [],
            "line_predictions": [],
            "metadata": {"config_name": config.name},
            "error": str(getattr(result, "error", "unknown error")),
        }

    ai_result = result.ai_result
    raw = ai_result.raw if isinstance(ai_result.raw, dict) else {}
    measurements = [
        {
            "name": measurement.name,
            "value": measurement.value,
            "unit": measurement.unit,
            "source": measurement.source,
        }
        for measurement in ai_result.measurements
    ]
    line_predictions = []
    for entry in raw.get("line_predictions", []) if isinstance(raw.get("line_predictions", []), list) else []:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        line_predictions.append(
            {
                "order": entry.get("order"),
                "text": text,
                "confidence": entry.get("confidence"),
                "parser_source": entry.get("parser_source"),
            }
        )
    return {
        "dicom_path": _canonical_path(path),
        "status": "ok",
        "measurements": measurements,
        "line_predictions": line_predictions,
        "metadata": {
            "config_name": config.name,
            "model_name": ai_result.model_name,
            "record_count": raw.get("record_count", 0),
            "line_prediction_count": len(raw.get("line_predictions", []))
            if isinstance(raw.get("line_predictions", []), list)
            else 0,
            "parser_sources": raw.get("parser_sources", []),
            "source_kinds": raw.get("source_kinds", []),
        },
        "error": None,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _checkpoint_path_for(config_dir: Path) -> Path:
    return config_dir / "checkpoint.json"


def _load_checkpoint(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.exists():
        return [], {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    manifest = payload.get("manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    return [item for item in items if isinstance(item, dict)], manifest


def _write_checkpoint(
    path: Path,
    *,
    config: SweepConfig,
    items: list[dict[str, Any]],
    engine: str,
    parser_mode: str,
    input_path: Path,
    started_at: str,
    elapsed_s: float,
    ok_files: int,
    error_files: int,
) -> None:
    payload = {
        "manifest": {
            "run_type": "preprocess_sweep_checkpoint",
            "config_name": config.name,
            "config": asdict(config),
            "engine": engine,
            "parser_mode": parser_mode,
            "input_path": _canonical_path(input_path),
            "started_at": started_at,
            "elapsed_s": round(elapsed_s, 3),
            "processed_files": len(items),
            "ok_files": ok_files,
            "error_files": error_files,
            "updated_at": _iso_now(),
            "pid": os.getpid(),
        },
        "items": items,
    }
    _write_json(path, payload)


def _clean_checkpoint(path: Path) -> None:
    if path.exists():
        path.unlink()


def _result_error_item(path: Path, config: SweepConfig, error_type: str, message: str) -> dict[str, Any]:
    return {
        "dicom_path": _canonical_path(path),
        "status": "error",
        "measurements": [],
        "line_predictions": [],
        "metadata": {"config_name": config.name},
        "error": {"type": error_type, "message": message},
    }


def _alarm_handler(_signum: int, _frame: Any) -> None:
    raise PerFileTimeoutError("Per-DICOM timeout reached.")


def _run_with_timeout(timeout_s: int, func: Callable[[], Any]) -> Any:
    if timeout_s <= 0:
        return func()
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0.0)
    try:
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
        return func()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _dispose_engine(engine: Any) -> None:
    stop = getattr(engine, "_stop_worker", None)
    if callable(stop):
        try:
            stop()
        except Exception:
            pass
    primary = getattr(engine, "primary", None)
    if primary is not None:
        _dispose_engine(primary)
    fallback = getattr(engine, "fallback", None)
    if fallback is not None:
        _dispose_engine(fallback)


def _dispose_pipeline(pipeline: EchoOcrPipeline | None) -> None:
    if pipeline is None:
        return
    _dispose_engine(getattr(pipeline, "ocr_engine", None))
    _dispose_engine(getattr(pipeline, "_fallback_ocr_engine", None))


def _score_labeled_subset(
    items: list[dict[str, Any]],
    labeled_files: list[LabeledFile],
) -> dict[str, Any]:
    item_by_path = {str(item.get("dicom_path", "")).strip(): item for item in items}
    file_details: list[dict[str, Any]] = []
    total_labels = 0
    total_full = 0
    total_line = 0
    total_value = 0
    total_label = 0
    total_prefix = 0
    files_with_predictions = 0

    for labeled in labeled_files:
        key = _canonical_path(labeled.path)
        item = item_by_path.get(key)
        predicted_measurements = item.get("measurements", []) if isinstance(item, dict) else []
        predictions: list[dict[str, str | None]] = []
        seen_prediction_keys: set[tuple[str, str, str]] = set()

        def _append_prediction(name: str | None, value: str | None, unit: str | None) -> None:
            prediction = {
                "name": name,
                "value": value,
                "unit": unit,
            }
            dedupe_key = (
                str(prediction["name"] or "").strip().lower(),
                str(prediction["value"] or "").strip().lower(),
                str(prediction["unit"] or "").strip().lower(),
            )
            if dedupe_key in seen_prediction_keys:
                return
            seen_prediction_keys.add(dedupe_key)
            predictions.append(prediction)

        for measurement in predicted_measurements if isinstance(predicted_measurements, list) else []:
            if not isinstance(measurement, dict):
                continue
            def _clean_value(key: str) -> str | None:
                raw = measurement.get(key)
                if raw is None:
                    return None
                text = str(raw).strip()
                return text or None

            _append_prediction(
                _clean_value("name"),
                _clean_value("value"),
                _clean_value("unit"),
            )

        raw_lines = item.get("line_predictions", []) if isinstance(item, dict) else []
        for line in raw_lines if isinstance(raw_lines, list) else []:
            if not isinstance(line, dict):
                continue
            line_text = str(line.get("text") or "").strip()
            if not line_text:
                continue
            _append_prediction(line_text, None, None)

        if predictions:
            files_with_predictions += 1

        matches = score_predictions(labeled.measurements, predictions)
        label_count = len(labeled.measurements)
        full_count = sum(1 for item in matches if item.full_match)
        line_count = sum(1 for item in matches if item.line_match)
        value_count = sum(1 for item in matches if item.value_match)
        match_label_count = sum(1 for item in matches if item.label_match)
        prefix_count = sum(1 for item in matches if item.prefix_match)

        total_labels += label_count
        total_full += full_count
        total_line += line_count
        total_value += value_count
        total_label += match_label_count
        total_prefix += prefix_count

        file_details.append(
            {
                "file_path": key,
                "file_name": labeled.file_name,
                "split": labeled.split,
                "status": str(item.get("status", "missing")) if isinstance(item, dict) else "missing",
                "error": item.get("error") if isinstance(item, dict) else "missing headless result",
                "expected_lines": [measurement.text for measurement in labeled.measurements],
                "predicted_measurements": predictions,
                "exact_matches": full_count,
                "line_matches": line_count,
                "value_matches": value_count,
                "label_matches": match_label_count,
                "prefix_matches": prefix_count,
                "total_labels": label_count,
                "matches": [
                    {
                        "expected_text": match.expected_text,
                        "predicted_text": match.predicted_text,
                        "line_match": match.line_match,
                        "prefix_match": match.prefix_match,
                        "label_match": match.label_match,
                        "value_match": match.value_match,
                        "unit_match": match.unit_match,
                        "full_match": match.full_match,
                    }
                    for match in matches
                ],
            }
        )

    labeled_file_count = len(labeled_files)
    return {
        "labeled_files": labeled_file_count,
        "files_with_predictions": files_with_predictions,
        "total_labels": total_labels,
        "exact_matches": total_full,
        "line_matches": total_line,
        "value_matches": total_value,
        "label_matches": total_label,
        "prefix_matches": total_prefix,
        "exact_match_rate": total_full / max(total_labels, 1),
        "line_match_rate": total_line / max(total_labels, 1),
        "value_match_rate": total_value / max(total_labels, 1),
        "label_match_rate": total_label / max(total_labels, 1),
        "prefix_match_rate": total_prefix / max(total_labels, 1),
        "detection_rate": files_with_predictions / max(labeled_file_count, 1),
        "file_details": file_details,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep preprocessing variants with the headless Echo OCR pipeline, save per-config "
            "JSON outputs for all DICOMs, and score the labeled subset against labels/labels.json."
        )
    )
    parser.add_argument("input_path", type=Path, help="DICOM file or directory root.")
    parser.add_argument("--pattern", default="*.dcm", help="Glob pattern for DICOM discovery.")
    parser.add_argument("--recursive", action="store_true", help="Use recursive discovery.")
    parser.add_argument("--max-files", type=int, default=0, help="Optional cap for discovery.")
    parser.add_argument(
        "--engine",
        default="tesseract",
        help="OCR engine to keep fixed during the sweep (default: tesseract).",
    )
    parser.add_argument(
        "--parser-mode",
        default="off",
        help="Parser mode passed to EchoOcrPipeline (default: off).",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=DEFAULT_LABELS_PATH,
        help="Ground-truth labels JSON used for scoring the labeled subset.",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Optional label split filter, e.g. validation or train,validation.",
    )
    parser.add_argument(
        "--config-set",
        choices=("smoke", "broad"),
        default="broad",
        help="Predefined preprocessing sweep set.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write per-config artifacts and summary files.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip configs whose headless.json already exists in output-dir.",
    )
    parser.add_argument(
        "--resume-configs",
        action="store_true",
        help="Resume inside an in-progress config from checkpoint.json if present.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional frame cap passed to PipelineRequest.",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Write per-config checkpoint every N processed files (default: 10).",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10,
        help="Print progress every N processed files (default: 10).",
    )
    parser.add_argument(
        "--per-file-timeout-s",
        type=int,
        default=180,
        help="Fail and continue if one DICOM takes longer than this many seconds (0 disables timeout).",
    )
    parser.add_argument(
        "--only-configs",
        default="",
        help="Optional comma-separated config names to run.",
    )
    parser.add_argument(
        "--exclude-configs",
        default="",
        help="Optional comma-separated config names to skip.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input_path.expanduser()
    if not input_path.exists():
        print(f"Input path not found: {input_path}")
        return 2

    discovered = _discover_files(input_path, args.pattern, args.recursive)
    if args.max_files > 0:
        discovered = discovered[: args.max_files]
    if not discovered:
        print("No matching DICOM files found.")
        return 1

    labels_path = args.labels.expanduser()
    if not labels_path.exists():
        print(f"Labels file not found: {labels_path}")
        return 2

    label_splits = parse_requested_splits(args.split)
    labeled_files = parse_labels(labels_path, split_filter=label_splits)
    discovered_keys = {_canonical_path(path) for path in discovered}
    labeled_files = [item for item in labeled_files if _canonical_path(item.path) in discovered_keys]

    output_dir = args.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    configs = _filter_configs(
        _select_configs(args.config_set),
        only_configs=args.only_configs,
        exclude_configs=args.exclude_configs,
    )
    if not configs:
        print("No configs selected after filtering.")
        return 1
    print(f"Discovered DICOM files: {len(discovered)}")
    print(f"Labeled files in scope: {len(labeled_files)}")
    print(f"Configs to run: {len(configs)}")

    summary_rows: list[dict[str, Any]] = []
    summary_payload: list[dict[str, Any]] = []

    for index, config in enumerate(configs, start=1):
        config_dir = output_dir / config.name
        headless_path = config_dir / "headless.json"
        score_path = config_dir / "label_scores.json"
        checkpoint_path = _checkpoint_path_for(config_dir)
        if args.skip_existing and headless_path.exists() and score_path.exists():
            print(f"[{index}/{len(configs)}] skip existing: {config.name}")
            score_payload = json.loads(score_path.read_text(encoding="utf-8"))
            summary = score_payload.get("summary", {})
            summary_rows.append(
                {
                    "config_name": config.name,
                    "engine": args.engine,
                    "description": config.description,
                    "exact_match_rate": summary.get("exact_match_rate", 0.0),
                    "line_match_rate": summary.get("line_match_rate", 0.0),
                    "value_match_rate": summary.get("value_match_rate", 0.0),
                    "label_match_rate": summary.get("label_match_rate", 0.0),
                    "prefix_match_rate": summary.get("prefix_match_rate", 0.0),
                    "detection_rate": summary.get("detection_rate", 0.0),
                    "elapsed_s": summary.get("elapsed_s", 0.0),
                    "processed_files": summary.get("processed_files", 0),
                    "ok_files": summary.get("ok_files", 0),
                    "error_files": summary.get("error_files", 0),
                }
            )
            summary_payload.append(score_payload)
            continue

        print(f"[{index}/{len(configs)}] {config.name}")
        config_dir.mkdir(parents=True, exist_ok=True)
        started_at = _iso_now()
        elapsed_before = 0.0
        items: list[dict[str, Any]] = []
        if args.resume_configs and checkpoint_path.exists():
            items, checkpoint_manifest = _load_checkpoint(checkpoint_path)
            elapsed_before = float(checkpoint_manifest.get("elapsed_s", 0.0) or 0.0)
            started_at = str(checkpoint_manifest.get("started_at", started_at))
            print(f"  resumed checkpoint with {len(items)} processed files")

        processed_keys = {
            str(item.get("dicom_path", "")).strip()
            for item in items
            if str(item.get("dicom_path", "")).strip()
        }
        ok_files = sum(1 for item in items if item.get("status") == "ok")
        error_files = sum(1 for item in items if item.get("status") == "error")
        pending = [path for path in discovered if _canonical_path(path) not in processed_keys]
        started = time.perf_counter()
        pipeline: EchoOcrPipeline | None = _build_pipeline(args.engine, args.parser_mode, config)

        try:
            for path in pending:
                try:
                    result = _run_with_timeout(
                        int(args.per_file_timeout_s),
                        lambda _path=path, _pipeline=pipeline: _pipeline.run(
                            PipelineRequest(
                                dicom_path=_path,
                                parameters={"max_frames": args.max_frames},
                            )
                        ),
                    )
                    item = _result_to_item(path, result, config)
                except PerFileTimeoutError as exc:
                    item = _result_error_item(path, config, "Timeout", str(exc))
                    _dispose_pipeline(pipeline)
                    pipeline = _build_pipeline(args.engine, args.parser_mode, config)
                except KeyboardInterrupt:
                    elapsed_partial = elapsed_before + (time.perf_counter() - started)
                    _write_checkpoint(
                        checkpoint_path,
                        config=config,
                        items=items,
                        engine=args.engine,
                        parser_mode=args.parser_mode,
                        input_path=input_path,
                        started_at=started_at,
                        elapsed_s=elapsed_partial,
                        ok_files=ok_files,
                        error_files=error_files,
                    )
                    _dispose_pipeline(pipeline)
                    raise
                except Exception as exc:
                    item = _result_error_item(path, config, type(exc).__name__, str(exc))
                    _dispose_pipeline(pipeline)
                    pipeline = _build_pipeline(args.engine, args.parser_mode, config)

                items.append(item)
                if item["status"] == "ok":
                    ok_files += 1
                else:
                    error_files += 1

                processed_count = len(items)
                if (
                    processed_count % int(args.checkpoint_interval) == 0
                    or processed_count == len(discovered)
                ):
                    elapsed_partial = elapsed_before + (time.perf_counter() - started)
                    _write_checkpoint(
                        checkpoint_path,
                        config=config,
                        items=items,
                        engine=args.engine,
                        parser_mode=args.parser_mode,
                        input_path=input_path,
                        started_at=started_at,
                        elapsed_s=elapsed_partial,
                        ok_files=ok_files,
                        error_files=error_files,
                    )

                if processed_count % int(args.progress_interval) == 0 or processed_count == len(discovered):
                    print(
                        f"  files {processed_count}/{len(discovered)} "
                        f"ok={ok_files} error={error_files} "
                        f"last={path.name}"
                    )
        finally:
            _dispose_pipeline(pipeline)

        elapsed = elapsed_before + (time.perf_counter() - started)
        headless_payload = {
            "manifest": {
                "run_type": "preprocess_sweep_headless",
                "config_name": config.name,
                "config": asdict(config),
                "engine": args.engine,
                "parser_mode": args.parser_mode,
                "started_at": started_at,
                "elapsed_s": round(elapsed, 3),
                "input_path": _canonical_path(input_path),
                "summary": {
                    "processed_files": len(discovered),
                    "ok_files": ok_files,
                    "error_files": error_files,
                },
            },
            "items": items,
        }
        _write_json(headless_path, headless_payload)
        _clean_checkpoint(checkpoint_path)

        label_scores = _score_labeled_subset(items, labeled_files)
        score_payload = {
            "manifest": {
                "run_type": "preprocess_sweep_label_scores",
                "config_name": config.name,
                "config": asdict(config),
                "engine": args.engine,
                "labels_path": _canonical_path(labels_path),
                "split_filter": sorted(label_splits),
            },
            "summary": {
                **{key: value for key, value in label_scores.items() if key != "file_details"},
                "elapsed_s": round(elapsed, 3),
                "processed_files": len(discovered),
                "ok_files": ok_files,
                "error_files": error_files,
            },
            "file_details": label_scores["file_details"],
        }
        _write_json(score_path, score_payload)
        summary_payload.append(score_payload)

        summary_rows.append(
            {
                "config_name": config.name,
                "engine": args.engine,
                "description": config.description,
                "exact_match_rate": label_scores["exact_match_rate"],
                "line_match_rate": label_scores["line_match_rate"],
                "value_match_rate": label_scores["value_match_rate"],
                "label_match_rate": label_scores["label_match_rate"],
                "prefix_match_rate": label_scores["prefix_match_rate"],
                "detection_rate": label_scores["detection_rate"],
                "elapsed_s": round(elapsed, 3),
                "processed_files": len(discovered),
                "ok_files": ok_files,
                "error_files": error_files,
            }
        )

    baseline_name = "default_multiview"
    baseline_row = next((row for row in summary_rows if row["config_name"] == baseline_name), None)
    baseline_exact = float(baseline_row["exact_match_rate"]) if baseline_row is not None else None
    for row in summary_rows:
        row["delta_exact_vs_default_multiview"] = (
            round(float(row["exact_match_rate"]) - baseline_exact, 6)
            if baseline_exact is not None
            else ""
        )

    summary_rows = sorted(
        summary_rows,
        key=lambda row: (
            float(row["exact_match_rate"]),
            float(row["value_match_rate"]),
            -float(row["elapsed_s"]),
        ),
        reverse=True,
    )

    summary_json = {
        "manifest": {
            "run_type": "preprocess_sweep_summary",
            "input_path": _canonical_path(input_path),
            "labels_path": _canonical_path(labels_path),
            "engine": args.engine,
            "parser_mode": args.parser_mode,
            "config_set": args.config_set,
            "config_count": len(configs),
            "file_count": len(discovered),
            "labeled_file_count": len(labeled_files),
        },
        "results": summary_rows,
    }
    _write_json(output_dir / "summary.json", summary_json)
    _write_csv(
        output_dir / "summary.csv",
        summary_rows,
        [
            "config_name",
            "engine",
            "description",
            "exact_match_rate",
            "line_match_rate",
            "value_match_rate",
            "label_match_rate",
            "prefix_match_rate",
            "detection_rate",
            "delta_exact_vs_default_multiview",
            "elapsed_s",
            "processed_files",
            "ok_files",
            "error_files",
        ],
    )

    if summary_rows:
        best = summary_rows[0]
        print("\nBest config")
        print(
            f"  {best['config_name']}: exact={best['exact_match_rate']:.3f} "
            f"value={best['value_match_rate']:.3f} elapsed={best['elapsed_s']:.1f}s"
        )
    print(f"Summary written to: {output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
