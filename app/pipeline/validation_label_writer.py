from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.types import AiMeasurement


DATASET_VERSION = 1
DATASET_TASK = "exact_roi_measurement_transcription"
DEFAULT_SPLIT = "validation"


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

    def _load_payload(self) -> dict[str, Any]:
        if not self._output_path.exists():
            return self._empty_payload()

        payload = json.loads(self._output_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Label file must contain a top-level JSON object.")

        version = payload.get("version")
        if version != DATASET_VERSION:
            raise ValueError(
                f"Unsupported label dataset version: {version!r}. Expected {DATASET_VERSION}."
            )

        task = payload.get("task")
        if task != DATASET_TASK:
            raise ValueError(
                f"Unsupported label dataset task: {task!r}. Expected {DATASET_TASK!r}."
            )

        files = payload.get("files")
        if not isinstance(files, list):
            raise ValueError("Label dataset must contain a 'files' array.")

        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        files = payload.get("files", [])
        if isinstance(files, list):
            files.sort(
                key=lambda item: (
                    str(item.get("split", "")) if isinstance(item, dict) else "",
                    str(item.get("file_name", "")) if isinstance(item, dict) else "",
                    str(item.get("file_path", "")) if isinstance(item, dict) else "",
                )
            )

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        ordered_measurements: list[dict[str, Any]] = []

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
    def _upsert_file_record(payload: dict[str, Any], record: dict[str, Any]) -> None:
        files = payload.get("files")
        if not isinstance(files, list):
            raise ValueError("Label dataset must contain a 'files' array.")

        record_path = str(record.get("file_path", "")).strip()
        if not record_path:
            raise ValueError("File record is missing a non-empty 'file_path'.")

        for index, existing in enumerate(files):
            if not isinstance(existing, dict):
                continue
            if str(existing.get("file_path", "")).strip() == record_path:
                files[index] = record
                return

        files.append(record)

    @staticmethod
    def _measurement_to_text(measurement: str | AiMeasurement) -> str:
        if isinstance(measurement, str):
            return ValidationLabelWriter._normalize_line(measurement)

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
        line = " ".join(value.split()).strip()
        if not line:
            return ""
        line = line.replace("\\,", " ")
        line = line.replace("\\%", " %")
        line = line.replace("\\text{", "")
        line = line.replace("\\mathrm{", "")
        line = line.replace("}", "")
        return " ".join(line.split())

    @staticmethod
    def _normalize_split(split: str) -> str:
        cleaned = " ".join(str(split).split()).strip().lower()
        if not cleaned:
            raise ValueError("Split must be a non-empty string.")
        return cleaned
