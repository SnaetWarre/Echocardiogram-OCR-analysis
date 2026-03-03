from __future__ import annotations

from pathlib import Path

from app.models.types import AiMeasurement, ValidationSession


def test_validation_session_tracks_accuracy_and_labels() -> None:
    session = ValidationSession()
    assert session.total_reviewed_measurements == 0
    assert session.accuracy == 0.0

    session.total_ai_correct += 2
    session.total_ai_incorrect += 1
    session.session_labels.append(
        (Path("/tmp/example.dcm"), [AiMeasurement(name="TR Vmax", value="2.1", unit="m/s")])
    )

    assert session.total_reviewed_measurements == 3
    assert session.accuracy == 2 / 3
    assert len(session.session_labels) == 1
