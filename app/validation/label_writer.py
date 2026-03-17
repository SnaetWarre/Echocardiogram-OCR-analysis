from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict, cast

from app.models.types import AiMeasurement
from app.pipeline.measurement_decoder import canonicalize_exact_line, extract_line_from_source
from app.validation.datasets import DATASET_TASK, DATASET_VERSION


DEFAULT_SPLIT = "validation"


class MeasurementEntry(TypedDict):
    order: int
    text: str


class FileEntry(TypedDict):
    file_name: str
    file_path: str
    split: str
    measurements: list[MeasurementEntry]


class LabelDataset(TypedDict):
    version: int
    task: str
    files: list[FileEntry]


class ValidationLabelWriter:
    def __init__(
        self,
        output_path: Path | None = None,
        *,
        split: str = DEFAULT_SPLIT,
    ) -> None:
        self._output_path = output_path or (Path.cwd() / "labels" / "exact_lines.json")
        self._split = self._normalize_split(split)

    @property
    def output_path(self) -> Path:
        return self._output_path

    @property
    def split(self) -> str:
        return self._split

    def append(self, dicom_path: Path, measurements: list[str | AiMeasurement]) -> Path:
        payload = self._load_payload()
        record = self._build_file_record(dicom_path, measurements, split=self._split)
        self._upsert_file_record(payload, record)
        self._write_payload(payload)
        return self._output_path

    def _load_payload(self) -> LabelDataset:
        if not self._output_path.exists():
            return self._empty_payload()

        payload = json.loads(self._output_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Label file must contain a top-level JSON object.")

        payload_obj = cast(dict[str, Any], payload)
        version = payload_obj.get("version")
        if version != DATASET_VERSION:
            raise ValueError(
                f"Unsupported label dataset version: {version!r}. Expected {DATASET_VERSION}."
            )

        task = payload_obj.get("task")
        if task != DATASET_TASK:
            raise ValueError(
                f"Unsupported label dataset task: {task!r}. Expected {DATASET_TASK!r}."
            )

        files = payload_obj.get("files")
        if not isinstance(files, list):
            raise ValueError("Label dataset must contain a 'files' array.")

        normalized_files: list[FileEntry] = []
        for item in cast(list[Any], files):
            if not isinstance(item, dict):
                continue
            file_obj = cast(dict[str, Any], item)
            measurements_raw = file_obj.get("measurements")
            measurements: list[MeasurementEntry] = []
            if isinstance(measurements_raw, list):
                for measurement in cast(list[Any], measurements_raw):
                    if not isinstance(measurement, dict):
                        continue
                    measurement_obj = cast(dict[str, Any], measurement)
                    order = measurement_obj.get("order")
                    text = str(measurement_obj.get("text", "")).strip()
                    if not isinstance(order, int) or not text:
                        continue
                    measurements.append({"order": order, "text": text})
            normalized_files.append(
                {
                    "file_name": str(file_obj.get("file_name", "")),
                    "file_path": str(file_obj.get("file_path", "")),
                    "split": str(file_obj.get("split", "")),
                    "measurements": measurements,
                }
            )

        return {
            "version": DATASET_VERSION,
            "task": DATASET_TASK,
            "files": normalized_files,
        }

    def _write_payload(self, payload: LabelDataset) -> None:
        payload["files"].sort(
            key=lambda item: (
                item["split"],
                item["file_name"],
                item["file_path"],
            )
        )
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _empty_payload() -> LabelDataset:
        return {
            "version": DATASET_VERSION,
            "task": DATASET_TASK,
            "files": [],
        }

    @staticmethod
    def _build_file_record(
        dicom_path: Path,
        measurements: list[str | AiMeasurement],
        *,
        split: str,
    ) -> FileEntry:
        ordered_measurements: list[MeasurementEntry] = []
        for index, measurement in enumerate(measurements, start=1):
            text = ValidationLabelWriter._measurement_to_text(measurement)
            if not text:
                continue
            ordered_measurements.append(
                {
                    "order": index,
                    "text": text,
                }
            )

        return {
            "file_name": dicom_path.name,
            "file_path": str(dicom_path),
            "split": ValidationLabelWriter._normalize_split(split),
            "measurements": ordered_measurements,
        }

    @staticmethod
    def _upsert_file_record(payload: LabelDataset, record: FileEntry) -> None:
        files = payload["files"]
        record_path = record["file_path"].strip()
        if not record_path:
            raise ValueError("File record is missing a non-empty 'file_path'.")

        for index, existing in enumerate(files):
            if existing["file_path"].strip() == record_path:
                files[index] = record
                return
        files.append(record)

    @staticmethod
    def _measurement_to_text(measurement: str | AiMeasurement) -> str:
        if isinstance(measurement, str):
            return ValidationLabelWriter._normalize_line(measurement)

        source_line = ValidationLabelWriter._extract_exact_line_from_source(measurement.source)
        if source_line:
            return ValidationLabelWriter._normalize_line(source_line)

        parts = [
            ValidationLabelWriter._normalize_token(measurement.name),
            ValidationLabelWriter._normalize_token(str(measurement.value)),
            ValidationLabelWriter._normalize_token(measurement.unit or ""),
        ]
        return ValidationLabelWriter._normalize_line(" ".join(part for part in parts if part))

    @staticmethod
    def _normalize_token(value: str) -> str:
        return " ".join(value.split()).strip()

    @staticmethod
    def _normalize_line(value: str) -> str:
        line = canonicalize_exact_line(value)
        if not line:
            return ""
        return " ".join(line.split())

    @staticmethod
    def _extract_exact_line_from_source(source: str | None) -> str | None:
        return extract_line_from_source(source)

    @staticmethod
    def _normalize_split(split: str) -> str:
        cleaned = " ".join(str(split).split()).strip().lower()
        if not cleaned:
            raise ValueError("Split must be a non-empty string.")
        return cleaned
