from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models.types import ValidatedLabelRecord, ValidationSession


def test_validation_session_tracks_accuracy_and_labels() -> None:
    session = ValidationSession()
    assert session.total_reviewed_measurements == 0
    assert session.accuracy == 0.0

    session.total_ai_correct += 2
    session.total_ai_incorrect += 1
    session.session_labels.append(
        ValidatedLabelRecord(
            path=Path("/tmp/example.dcm"),
            validated_at=datetime.now(),
            measurements=["TR Vmax 2.1 m/s"],
        )
    )

    assert session.total_reviewed_measurements == 3
    assert session.accuracy == 2 / 3
    assert len(session.session_labels) == 1
