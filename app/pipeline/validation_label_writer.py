from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from app.models.types import AiMeasurement


class ValidationLabelWriter:
    def __init__(self, output_path: Path | None = None) -> None:
        self._output_path = output_path or (Path.cwd() / "validation_labels.md")

    @property
    def output_path(self) -> Path:
        return self._output_path

    def append(self, dicom_path: Path, measurements: Sequence[str | AiMeasurement]) -> Path:
        block = self._format_block(dicom_path, measurements)
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "\n" if self._output_path.exists() and self._output_path.stat().st_size > 0 else ""
        with self._output_path.open("a", encoding="utf-8") as handle:
            handle.write(prefix)
            handle.write(block)
        return self._output_path

    @staticmethod
    def _format_block(dicom_path: Path, measurements: Sequence[str | AiMeasurement]) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        lines = [
            "--",
            f"path: {dicom_path}",
            f"validated_at: {timestamp}",
            "measurements:",
        ]
        for measurement in measurements:
            if isinstance(measurement, str):
                lines.append(f"-> {measurement}")
                continue
            name = " ".join(measurement.name.split())
            value = str(measurement.value).strip()
            unit = (measurement.unit or "").strip()
            suffix = f" {unit}" if unit else ""
            lines.append(f"-> {name} {value}{suffix}")
        if not measurements:
            lines.append("# no measurements retained")
        lines.append("")
        return "\n".join(lines)
