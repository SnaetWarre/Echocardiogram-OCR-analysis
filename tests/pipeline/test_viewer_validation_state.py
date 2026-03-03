from __future__ import annotations

from pathlib import Path

from app.models.types import AiMeasurement
from app.ui.state import ViewerState


def test_viewer_state_records_validation_metrics(monkeypatch) -> None:
    monkeypatch.setenv("DICOM_AI_ENABLED", "0")
    state = ViewerState()

    accuracy, is_new_high = state.record_validation(
        Path("/tmp/example-a.dcm"),
        approved_count=2,
        corrected_count=1,
        measurements=[AiMeasurement(name="TR Vmax", value="2.1", unit="m/s")],
    )
    assert is_new_high is True
    assert accuracy == 2 / 3
    assert state.validation_session.total_validated_frames == 1

    accuracy, is_new_high = state.record_validation(
        Path("/tmp/example-b.dcm"),
        approved_count=1,
        corrected_count=1,
        measurements=[],
    )
    assert is_new_high is False
    assert accuracy == 3 / 5
    assert state.validation_session.total_validated_frames == 2
