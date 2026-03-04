from __future__ import annotations

from pathlib import Path

from app.ui.validation_queue import build_validation_queue, collect_dicom_files


def test_validation_queue_starts_from_current_item() -> None:
    paths = [Path("/tmp/a.dcm"), Path("/tmp/b.dcm"), Path("/tmp/c.dcm")]
    queue = build_validation_queue(paths, Path("/tmp/b.dcm"))
    assert queue == [Path("/tmp/b.dcm"), Path("/tmp/c.dcm")]


def test_validation_queue_includes_current_when_missing() -> None:
    paths = [Path("/tmp/a.dcm"), Path("/tmp/b.dcm")]
    queue = build_validation_queue(paths, Path("/tmp/x.dcm"))
    assert queue == [Path("/tmp/x.dcm"), Path("/tmp/a.dcm"), Path("/tmp/b.dcm")]


def test_collect_dicom_files_scans_nested_directories(tmp_path: Path) -> None:
    patient_dir = tmp_path / "patient_a"
    study_dir = patient_dir / "study_1"
    study_dir.mkdir(parents=True)
    file_one = study_dir / "frame_001.dcm"
    file_two = study_dir / "frame_002.DCM"
    file_three = patient_dir / "notes.txt"
    file_one.write_bytes(b"")
    file_two.write_bytes(b"")
    file_three.write_text("not a dicom", encoding="utf-8")

    files = collect_dicom_files(tmp_path)

    assert files == [file_one, file_two]
