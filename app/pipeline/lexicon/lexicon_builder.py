from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline.measurements.measurement_decoder import label_family_key, line_pattern, parse_measurement_line
from app.validation.datasets import DATASET_TASK, DATASET_VERSION


@dataclass(frozen=True)
class LexiconLineEntry:
    file_name: str
    file_path: str
    split: str
    order: int | None
    text: str


@dataclass(frozen=True)
class NumericStats:
    count: int
    min: float
    max: float
    mean: float


@dataclass
class LexiconArtifact:
    artifact_version: int
    created_at: str
    labels_path: str
    dataset_version: int
    dataset_task: str
    total_files: int
    total_lines: int
    split_counts: dict[str, int] = field(default_factory=dict)
    exact_line_frequencies: dict[str, int] = field(default_factory=dict)
    label_frequencies: dict[str, int] = field(default_factory=dict)
    label_family_lines: dict[str, list[str]] = field(default_factory=dict)
    label_unit_frequencies: dict[str, dict[str, int]] = field(default_factory=dict)
    label_order_frequencies: dict[str, dict[str, int]] = field(default_factory=dict)
    label_value_stats: dict[str, NumericStats] = field(default_factory=dict)
    token_frequencies: dict[str, int] = field(default_factory=dict)
    unit_frequencies: dict[str, int] = field(default_factory=dict)
    prefix_frequencies: dict[str, int] = field(default_factory=dict)
    line_pattern_frequencies: dict[str, int] = field(default_factory=dict)
    source_lines: list[LexiconLineEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["label_value_stats"] = {
            key: asdict(value)
            for key, value in self.label_value_stats.items()
        }
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LexiconArtifact":
        raw_value_stats = payload.get("label_value_stats", {})
        value_stats: dict[str, NumericStats] = {}
        if isinstance(raw_value_stats, dict):
            for key, value in raw_value_stats.items():
                if not isinstance(key, str) or not isinstance(value, dict):
                    continue
                try:
                    value_stats[key] = NumericStats(
                        count=int(value.get("count", 0)),
                        min=float(value.get("min", 0.0)),
                        max=float(value.get("max", 0.0)),
                        mean=float(value.get("mean", 0.0)),
                    )
                except (TypeError, ValueError):
                    continue

        raw_lines = payload.get("source_lines", [])
        source_lines: list[LexiconLineEntry] = []
        if isinstance(raw_lines, list):
            for item in raw_lines:
                if not isinstance(item, dict):
                    continue
                source_lines.append(
                    LexiconLineEntry(
                        file_name=str(item.get("file_name", "")),
                        file_path=str(item.get("file_path", "")),
                        split=str(item.get("split", "")),
                        order=int(item["order"]) if isinstance(item.get("order"), int) else None,
                        text=str(item.get("text", "")),
                    )
                )

        return cls(
            artifact_version=int(payload.get("artifact_version", 1)),
            created_at=str(payload.get("created_at", "")),
            labels_path=str(payload.get("labels_path", "")),
            dataset_version=int(payload.get("dataset_version", DATASET_VERSION)),
            dataset_task=str(payload.get("dataset_task", DATASET_TASK)),
            total_files=int(payload.get("total_files", 0)),
            total_lines=int(payload.get("total_lines", 0)),
            split_counts=_string_int_dict(payload.get("split_counts")),
            exact_line_frequencies=_string_int_dict(payload.get("exact_line_frequencies")),
            label_frequencies=_string_int_dict(payload.get("label_frequencies")),
            label_family_lines=_string_list_dict(payload.get("label_family_lines")),
            label_unit_frequencies=_nested_string_int_dict(payload.get("label_unit_frequencies")),
            label_order_frequencies=_nested_string_int_dict(payload.get("label_order_frequencies")),
            label_value_stats=value_stats,
            token_frequencies=_string_int_dict(payload.get("token_frequencies")),
            unit_frequencies=_string_int_dict(payload.get("unit_frequencies")),
            prefix_frequencies=_string_int_dict(payload.get("prefix_frequencies")),
            line_pattern_frequencies=_string_int_dict(payload.get("line_pattern_frequencies")),
            source_lines=source_lines,
        )

    def save(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def load(cls, input_path: Path) -> "LexiconArtifact":
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Lexicon artifact must contain a JSON object.")
        return cls.from_dict(payload)


def _string_int_dict(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        try:
            result[key] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def _string_list_dict(raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        result[key] = [str(item) for item in value if str(item).strip()]
    return result


def _nested_string_int_dict(raw: object) -> dict[str, dict[str, int]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, int]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        result[key] = _string_int_dict(value)
    return result


def _validate_dataset(payload: dict[str, object]) -> list[dict[str, object]]:
    version = payload.get("version")
    if version != DATASET_VERSION:
        raise ValueError(f"Unsupported label dataset version: {version!r}")
    task = payload.get("task")
    if task != DATASET_TASK:
        raise ValueError(f"Unsupported label dataset task: {task!r}")
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("Label dataset must contain a 'files' array.")
    return [item for item in files if isinstance(item, dict)]


def build_lexicon_artifact(labels_path: Path) -> LexiconArtifact:
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Label dataset must contain a top-level object.")
    file_records = _validate_dataset(payload)

    split_counts: Counter[str] = Counter()
    exact_lines: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    units: Counter[str] = Counter()
    prefixes: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    label_family_lines: dict[str, set[str]] = defaultdict(set)
    label_unit_frequencies: dict[str, Counter[str]] = defaultdict(Counter)
    label_order_frequencies: dict[str, Counter[str]] = defaultdict(Counter)
    label_values: dict[str, list[float]] = defaultdict(list)
    source_lines: list[LexiconLineEntry] = []
    total_lines = 0

    for file_record in file_records:
        file_name = str(file_record.get("file_name", "")).strip()
        file_path = str(file_record.get("file_path", "")).strip()
        split = str(file_record.get("split", "")).strip().lower()
        split_counts[split or "unknown"] += 1

        measurements = file_record.get("measurements")
        if not isinstance(measurements, list):
            continue

        for measurement in measurements:
            if not isinstance(measurement, dict):
                continue
            text = str(measurement.get("text", "")).strip()
            if not text:
                continue
            order = measurement.get("order")
            order_value = int(order) if isinstance(order, int) else None
            decoded = parse_measurement_line(text)
            exact_lines[decoded.canonical_text] += 1
            patterns[line_pattern(decoded.canonical_text)] += 1
            total_lines += 1
            source_lines.append(
                LexiconLineEntry(
                    file_name=file_name,
                    file_path=file_path,
                    split=split,
                    order=order_value,
                    text=decoded.canonical_text,
                )
            )

            if decoded.prefix is not None:
                prefixes[decoded.prefix] += 1
            if decoded.unit is not None:
                units[decoded.unit] += 1
            if decoded.label is not None:
                family = label_family_key(decoded.label)
                labels[family] += 1
                label_family_lines[family].add(decoded.canonical_text)
                if decoded.unit is not None:
                    label_unit_frequencies[family][decoded.unit] += 1
                if order_value is not None:
                    label_order_frequencies[family][str(order_value)] += 1
                if decoded.value is not None:
                    try:
                        label_values[family].append(float(decoded.value))
                    except ValueError:
                        pass
                for token in decoded.label.split():
                    tokens[token.lower()] += 1

    label_value_stats = {
        key: NumericStats(
            count=len(values),
            min=min(values),
            max=max(values),
            mean=sum(values) / len(values),
        )
        for key, values in label_values.items()
        if values
    }

    return LexiconArtifact(
        artifact_version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        labels_path=str(labels_path),
        dataset_version=DATASET_VERSION,
        dataset_task=DATASET_TASK,
        total_files=len(file_records),
        total_lines=total_lines,
        split_counts=dict(split_counts),
        exact_line_frequencies=dict(exact_lines),
        label_frequencies=dict(labels),
        label_family_lines={key: sorted(values) for key, values in label_family_lines.items()},
        label_unit_frequencies={key: dict(value) for key, value in label_unit_frequencies.items()},
        label_order_frequencies={key: dict(value) for key, value in label_order_frequencies.items()},
        label_value_stats=label_value_stats,
        token_frequencies=dict(tokens),
        unit_frequencies=dict(units),
        prefix_frequencies=dict(prefixes),
        line_pattern_frequencies=dict(patterns),
        source_lines=source_lines,
    )
