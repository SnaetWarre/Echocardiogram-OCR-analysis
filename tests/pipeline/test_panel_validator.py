from __future__ import annotations

from app.models.types import AiMeasurement
from app.pipeline.line_transcriber import LinePrediction, PanelTranscription
from app.pipeline.panel_validator import LocalLlmPanelValidator, PanelValidatorConfig


def _panel(*, uncertain: bool = True) -> PanelTranscription:
    return PanelTranscription(
        lines=(
            LinePrediction(
                order=0,
                bbox=(0, 0, 20, 4),
                text="TR Vmax 2.1 m/s",
                confidence=0.72,
                engine_name="ocr",
                source="primary",
                uncertain=uncertain,
            ),
        ),
        combined_text="TR Vmax 2.1 m/s",
        uncertain_line_count=1 if uncertain else 0,
    )


def test_panel_validator_selectively_refines_measurements() -> None:
    validator = LocalLlmPanelValidator(
        config=PanelValidatorConfig(mode="selective"),
        runner=lambda _prompt: '{"measurements":[{"order":1,"name":"TR Vmax","value":"2.1","unit":"m/s"}]}',
    )

    result = validator.validate(
        _panel(uncertain=True),
        [AiMeasurement(name="TR Vmax", value="2.1", unit="ms", order_hint=0)],
        confidence=0.8,
    )

    assert result.applied is True
    assert result.measurements[0].name == "TR Vmax"
    assert result.measurements[0].unit == "m/s"
    assert result.measurements[0].order_hint == 0


def test_panel_validator_skips_stable_panels_without_uncertainty() -> None:
    validator = LocalLlmPanelValidator(
        config=PanelValidatorConfig(mode="selective"),
        runner=lambda _prompt: '{"measurements":[{"order":1,"name":"ignored","value":"1.0","unit":"cm"}]}',
    )

    result = validator.validate(
        _panel(uncertain=False),
        [AiMeasurement(name="TR Vmax", value="2.1", unit="m/s", order_hint=0)],
        confidence=0.8,
    )

    assert result.applied is False
    assert result.reason == "skipped"
