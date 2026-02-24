from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from app.pipeline.echo_ocr_schema import CSV_FIELDS, MeasurementRecord


class SidecarWriter:
    def __init__(
        self,
        output_dir: Path,
        *,
        write_csv: bool = True,
        write_jsonl: bool = True,
    ) -> None:
        self.output_dir = output_dir
        self.write_csv = write_csv
        self.write_jsonl = write_jsonl

    def write(self, study_key: str, records: Iterable[MeasurementRecord]) -> List[Path]:
        items = list(records)
        if not items:
            return []
        self.output_dir.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []
        if self.write_jsonl:
            jsonl_path = self.output_dir / f"{study_key}.measurements.jsonl"
            with jsonl_path.open("w", encoding="utf-8") as handle:
                for record in items:
                    handle.write(json.dumps(record.to_dict(), ensure_ascii=True) + "\n")
            written.append(jsonl_path)
        if self.write_csv:
            csv_path = self.output_dir / f"{study_key}.measurements.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for record in items:
                    writer.writerow(record.to_dict())
            written.append(csv_path)
        return written
