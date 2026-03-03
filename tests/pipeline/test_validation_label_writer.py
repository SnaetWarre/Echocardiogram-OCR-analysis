from __future__ import annotations

from pathlib import Path

from app.models.types import AiMeasurement
from app.pipeline.validation_label_writer import ValidationLabelWriter


def test_validation_label_writer_appends_records(tmp_path: Path) -> None:
    output_path = tmp_path / "validation_labels.md"
    writer = ValidationLabelWriter(output_path=output_path)

    writer.append(
        Path("/tmp/example_a.dcm"),
        [AiMeasurement(name="TR Vmax", value="2.1", unit="m/s")],
    )
    writer.append(Path("/tmp/example_b.dcm"), [])

    text = output_path.read_text(encoding="utf-8")
    assert text.count("--") == 2
    assert "path: /tmp/example_a.dcm" in text
    assert "-> TR Vmax 2.1 m/s" in text
    assert "path: /tmp/example_b.dcm" in text
    assert "# no measurements retained" in text
