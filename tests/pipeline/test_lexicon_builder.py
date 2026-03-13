from __future__ import annotations

import json
from pathlib import Path

from app.pipeline.lexicon_builder import LexiconArtifact, build_lexicon_artifact


def test_build_lexicon_artifact_collects_line_and_label_statistics(tmp_path: Path) -> None:
    labels_path = tmp_path / "exact_lines.json"
    labels_path.write_text(
        json.dumps(
            {
                "version": 1,
                "task": "exact_roi_measurement_transcription",
                "files": [
                    {
                        "file_name": "a.dcm",
                        "file_path": "/tmp/a.dcm",
                        "split": "validation",
                        "measurements": [
                            {"order": 1, "text": "1 IVSd 0.9 cm"},
                            {"order": 2, "text": "2 LVIDd 5.4 cm"},
                        ],
                    },
                    {
                        "file_name": "b.dcm",
                        "file_path": "/tmp/b.dcm",
                        "split": "train",
                        "measurements": [
                            {"order": 1, "text": "1 IVSd 1.0 cm"},
                        ],
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    artifact = build_lexicon_artifact(labels_path)

    assert artifact.total_files == 2
    assert artifact.total_lines == 3
    assert artifact.split_counts == {"validation": 1, "train": 1}
    assert artifact.exact_line_frequencies["1 IVSd 0.9 cm"] == 1
    assert artifact.label_frequencies["ivsd"] == 2
    assert artifact.label_unit_frequencies["ivsd"] == {"cm": 2}
    assert artifact.label_order_frequencies["ivsd"] == {"1": 2}
    assert artifact.label_value_stats["ivsd"].min == 0.9
    assert artifact.label_value_stats["ivsd"].max == 1.0


def test_lexicon_artifact_round_trips_through_json(tmp_path: Path) -> None:
    labels_path = tmp_path / "exact_lines.json"
    labels_path.write_text(
        json.dumps(
            {
                "version": 1,
                "task": "exact_roi_measurement_transcription",
                "files": [
                    {
                        "file_name": "a.dcm",
                        "file_path": "/tmp/a.dcm",
                        "split": "validation",
                        "measurements": [{"order": 1, "text": "1 IVSd 0.9 cm"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    artifact = build_lexicon_artifact(labels_path)
    output_path = tmp_path / "artifact.json"

    artifact.save(output_path)
    loaded = LexiconArtifact.load(output_path)

    assert loaded.total_files == artifact.total_files
    assert loaded.exact_line_frequencies == artifact.exact_line_frequencies
    assert loaded.label_frequencies == artifact.label_frequencies
