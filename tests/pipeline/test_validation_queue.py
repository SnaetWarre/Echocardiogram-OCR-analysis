from __future__ import annotations

from pathlib import Path

from app.ui.validation_queue import build_validation_queue


def test_validation_queue_starts_from_current_item() -> None:
    paths = [Path("/tmp/a.dcm"), Path("/tmp/b.dcm"), Path("/tmp/c.dcm")]
    queue = build_validation_queue(paths, Path("/tmp/b.dcm"))
    assert queue == [Path("/tmp/b.dcm"), Path("/tmp/c.dcm")]


def test_validation_queue_includes_current_when_missing() -> None:
    paths = [Path("/tmp/a.dcm"), Path("/tmp/b.dcm")]
    queue = build_validation_queue(paths, Path("/tmp/x.dcm"))
    assert queue == [Path("/tmp/x.dcm"), Path("/tmp/a.dcm"), Path("/tmp/b.dcm")]
