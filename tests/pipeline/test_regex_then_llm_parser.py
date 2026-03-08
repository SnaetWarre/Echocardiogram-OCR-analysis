from __future__ import annotations

from app.models.types import AiMeasurement
from app.pipeline.measurement_parsers import RegexMeasurementParser, RegexThenLlmMeasurementParser


class _FakeLlmParser:
    def __init__(self, items: list[AiMeasurement]) -> None:
        self._items = items
        self.calls = 0

    def parse(self, text: str, *, confidence: float) -> list[AiMeasurement]:
        _ = text
        _ = confidence
        self.calls += 1
        return list(self._items)


def test_regex_then_llm_prefers_regex_when_available() -> None:
    llm = _FakeLlmParser([AiMeasurement(name="fallback", value="1.0", unit="cm")])
    parser = RegexThenLlmMeasurementParser(RegexMeasurementParser(), llm)

    items = parser.parse("TR Vmax 1.9 m/s", confidence=0.9)

    assert len(items) == 1
    assert items[0].name == "TR Vmax"
    assert items[0].value == "1.9"
    assert items[0].unit == "m/s"
    assert llm.calls == 0


def test_regex_then_llm_falls_back_when_regex_finds_nothing() -> None:
    llm = _FakeLlmParser([AiMeasurement(name="TR Vmax", value="1.9", unit="m/s")])
    parser = RegexThenLlmMeasurementParser(RegexMeasurementParser(), llm)

    items = parser.parse("nonsense overlay text", confidence=0.9)

    assert len(items) == 1
    assert items[0].name == "TR Vmax"
    assert llm.calls == 1
