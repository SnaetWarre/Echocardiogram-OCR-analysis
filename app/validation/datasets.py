from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.repo_paths import DEFAULT_EXACT_LINES_PATH, PROJECT_ROOT


DATASET_VERSION = 1
DATASET_TASK = "exact_roi_measurement_transcription"
DEFAULT_LABELS_PATH = DEFAULT_EXACT_LINES_PATH

_LINE_UNIT_RE = r"%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2"


@dataclass
class LabeledMeasurement:
    text: str
    order: int | None = None


@dataclass
class LabeledFile:
    path: Path
    file_name: str
    split: str
    measurements: list[LabeledMeasurement] = field(default_factory=list)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_split_name(value: str | None) -> str:
    return normalize_space(value or "").lower()


def split_matches(record_split: str, requested_splits: set[str]) -> bool:
    if not requested_splits:
        return True
    return normalize_split_name(record_split) in requested_splits


def canonicalize_label_line(text: str) -> str:
    line = normalize_space(text)
    line = line.replace(r"\,", " ")
    line = line.replace(r"\%", " %")
    line = re.sub(r"\\text\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\bm/s\s*2\b", "m/s2", line, flags=re.IGNORECASE)
    line = re.sub(r"\bcm\s*2\b", "cm2", line, flags=re.IGNORECASE)
    line = re.sub(r"\bml/m\s*2\b", "ml/m2", line, flags=re.IGNORECASE)
    line = re.sub(r"\s+([%])", r" \1", line)
    line = re.sub(rf"(\d)({_LINE_UNIT_RE})\b", r"\1 \2", line)
    return normalize_space(line)


def _resolve_home_relative_documents_path(raw_path: str) -> Path | None:
    normalized = raw_path.strip().replace("\\", "/")
    if not normalized:
        return None

    if normalized.startswith("~/"):
        return Path(normalized).expanduser().resolve()

    match = re.match(r"^/(?:home|Users)/[^/]+/Documents(?:/(.*))?$", normalized)
    if match is None:
        return None

    documents_root = Path.home() / "Documents"
    remainder = match.group(1) or ""
    if not remainder:
        return documents_root.resolve()
    return (documents_root.joinpath(*[part for part in remainder.split("/") if part])).resolve()


def resolve_dataset_path(file_record: dict[str, Any], dataset_path: Path) -> Path:
    raw_path = str(file_record.get("file_path", "")).strip()
    if not raw_path:
        raise ValueError("Dataset entry is missing a non-empty 'file_path'.")

    migrated_home_path = _resolve_home_relative_documents_path(raw_path)
    if migrated_home_path is not None:
        return migrated_home_path

    path = Path(raw_path).expanduser()
    if path.is_absolute() or raw_path.startswith(("/", "\\")):
        return path.resolve()
    return (PROJECT_ROOT / raw_path).resolve()


def parse_requested_splits(raw: str) -> set[str]:
    return {
        normalize_split_name(item)
        for item in raw.split(",")
        if normalize_split_name(item)
    }


def parse_labels(labels_path: Path, *, split_filter: set[str] | None = None) -> list[LabeledFile]:
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Labels file must contain a top-level JSON object.")

    version = payload.get("version")
    if version != DATASET_VERSION:
        raise ValueError(
            f"Unsupported dataset version: {version!r} (expected {DATASET_VERSION})."
        )

    task = payload.get("task")
    if task != DATASET_TASK:
        raise ValueError(
            f"Unsupported dataset task: {task!r} (expected {DATASET_TASK!r})."
        )

    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("Labels file must contain a 'files' array.")

    requested_splits = split_filter or set()
    results: list[LabeledFile] = []

    for index, file_record in enumerate(files):
        if not isinstance(file_record, dict):
            raise ValueError(f"File record at index {index} must be an object.")

        file_name = str(file_record.get("file_name", "")).strip()
        file_path = resolve_dataset_path(file_record, labels_path)
        if not file_name:
            file_name = file_path.name

        split = str(file_record.get("split", "")).strip()
        if not split:
            raise ValueError(f"File record {file_name!r} is missing required 'split'.")

        if not split_matches(split, requested_splits):
            continue

        raw_measurements = file_record.get("measurements")
        if not isinstance(raw_measurements, list):
            raise ValueError(f"File record {file_name!r} must contain a 'measurements' array.")

        measurements: list[LabeledMeasurement] = []
        for measurement_index, measurement_record in enumerate(raw_measurements):
            if not isinstance(measurement_record, dict):
                raise ValueError(
                    f"Measurement record {measurement_index} for {file_name!r} must be an object."
                )
            text = str(measurement_record.get("text", "")).strip()
            if not text:
                continue
            order_raw = measurement_record.get("order")
            order = int(order_raw) if isinstance(order_raw, int) else None
            measurements.append(
                LabeledMeasurement(
                    text=canonicalize_label_line(text),
                    order=order,
                )
            )

        results.append(
            LabeledFile(
                path=file_path,
                file_name=file_name,
                split=split,
                measurements=measurements,
            )
        )

    return results
