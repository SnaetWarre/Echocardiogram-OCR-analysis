# pyright: reportMissingImports=false
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.types import AiMeasurement
from app.validation.datasets import DATASET_TASK, DATASET_VERSION
from app.validation.label_writer import ValidationLabelWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_empty_dataset(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": DATASET_VERSION,
                "task": DATASET_TASK,
                "files": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _make_dataset_with_record(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": DATASET_VERSION,
                "task": DATASET_TASK,
                "files": [
                    {
                        "file_name": "existing.dcm",
                        "file_path": "/tmp/existing.dcm",
                        "split": "train",
                        "measurements": [
                            {"order": 1, "text": "1 Existing Line 1.0 cm"},
                        ],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Basic write
# ---------------------------------------------------------------------------


def test_writer_creates_valid_json_dataset(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(
        Path("/tmp/example_a.dcm"),
        [AiMeasurement(name="TR Vmax", value="2.1", unit="m/s")],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["version"] == DATASET_VERSION
    assert payload["task"] == DATASET_TASK
    assert isinstance(payload["files"], list)
    assert len(payload["files"]) == 1

    record = payload["files"][0]
    assert record["file_name"] == "example_a.dcm"
    assert record["file_path"] == "/tmp/example_a.dcm"
    assert record["split"] == "validation"
    assert record["measurements"] == [
        {"order": 1, "text": "TR Vmax 2.1 m/s"},
    ]


def test_writer_records_empty_measurements(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(Path("/tmp/example_b.dcm"), [])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["measurements"] == []


def test_writer_preserves_literal_string_line(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(
        Path("/tmp/example_a.dcm"),
        ["1 Ao Desc Diam 2.0 cm2"],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["measurements"] == [
        {"order": 1, "text": "1 Ao Desc Diam 2.0 cm2"},
    ]


# ---------------------------------------------------------------------------
# Split field
# ---------------------------------------------------------------------------


def test_writer_uses_default_split(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(Path("/tmp/a.dcm"), [])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["split"] == "validation"


def test_writer_respects_custom_split(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path, split="train")

    writer.append(Path("/tmp/a.dcm"), [])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["split"] == "train"


def test_writer_normalizes_split_to_lowercase(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path, split="  Validation  ")

    writer.append(Path("/tmp/a.dcm"), [])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["split"] == "validation"


def test_writer_raises_on_empty_split(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ValidationLabelWriter(output_path=tmp_path / "exact_lines.json", split="")


# ---------------------------------------------------------------------------
# Append to existing dataset
# ---------------------------------------------------------------------------


def test_writer_appends_to_existing_dataset(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    _make_dataset_with_record(output_path)

    writer = ValidationLabelWriter(output_path=output_path)
    writer.append(
        Path("/tmp/new_file.dcm"),
        [AiMeasurement(name="2 New Label", value="3.4", unit="mmHg")],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(payload["files"]) == 2
    file_paths = [f["file_path"] for f in payload["files"]]
    assert "/tmp/existing.dcm" in file_paths
    assert "/tmp/new_file.dcm" in file_paths

    new_record = next(f for f in payload["files"] if f["file_path"] == "/tmp/new_file.dcm")
    assert new_record["measurements"] == [
        {"order": 1, "text": "2 New Label 3.4 mmHg"},
    ]


def test_writer_upserts_existing_file_record(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    _make_dataset_with_record(output_path)

    writer = ValidationLabelWriter(output_path=output_path, split="train")
    writer.append(
        Path("/tmp/existing.dcm"),
        [AiMeasurement(name="1 Updated Label", value="9.9", unit="cm")],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(payload["files"]) == 1
    record = payload["files"][0]
    assert record["measurements"] == [
        {"order": 1, "text": "1 Updated Label 9.9 cm"},
    ]


def test_writer_multiple_measurements_are_ordered(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(
        Path("/tmp/multi.dcm"),
        [
            AiMeasurement(name="1 IVSd", value="0.9", unit="cm"),
            AiMeasurement(name="2 LVIDd", value="5.4", unit="cm"),
            AiMeasurement(name="3 LVPWd", value="1.0", unit="cm"),
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    measurements = payload["files"][0]["measurements"]

    assert len(measurements) == 3
    assert measurements[0] == {"order": 1, "text": "1 IVSd 0.9 cm"}
    assert measurements[1] == {"order": 2, "text": "2 LVIDd 5.4 cm"}
    assert measurements[2] == {"order": 3, "text": "3 LVPWd 1.0 cm"}


def test_writer_prefers_exact_line_source_when_available(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(
        Path("/tmp/source_line.dcm"),
        [
            AiMeasurement(
                name="Ao Diam",
                value="3.2",
                unit="cm",
                source="exact_line:1 Ao Diam 3.2 cm:0.997",
            )
        ],
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["files"][0]["measurements"] == [{"order": 1, "text": "1 Ao Diam 3.2 cm"}]


# ---------------------------------------------------------------------------
# Version / task validation
# ---------------------------------------------------------------------------


def test_writer_raises_on_wrong_version(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    output_path.write_text(
        json.dumps({"version": 99, "task": DATASET_TASK, "files": []}),
        encoding="utf-8",
    )

    writer = ValidationLabelWriter(output_path=output_path)
    with pytest.raises(ValueError, match="version"):
        writer.append(Path("/tmp/a.dcm"), [])


def test_writer_raises_on_wrong_task(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    output_path.write_text(
        json.dumps({"version": DATASET_VERSION, "task": "wrong_task", "files": []}),
        encoding="utf-8",
    )

    writer = ValidationLabelWriter(output_path=output_path)
    with pytest.raises(ValueError, match="task"):
        writer.append(Path("/tmp/a.dcm"), [])


# ---------------------------------------------------------------------------
# Dataset is sorted on write
# ---------------------------------------------------------------------------


def test_writer_sorts_files_by_split_then_name(tmp_path: Path) -> None:
    output_path = tmp_path / "exact_lines.json"
    writer_val = ValidationLabelWriter(output_path=output_path, split="validation")
    writer_train = ValidationLabelWriter(output_path=output_path, split="train")

    writer_val.append(Path("/tmp/z_val.dcm"), [])
    writer_val.append(Path("/tmp/a_val.dcm"), [])
    writer_train.append(Path("/tmp/m_train.dcm"), [])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    splits_and_names = [(f["split"], f["file_name"]) for f in payload["files"]]

    assert splits_and_names == sorted(splits_and_names)
