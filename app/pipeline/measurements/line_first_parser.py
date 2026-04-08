from __future__ import annotations

from typing import Iterable

from app.models.types import AiMeasurement
from app.pipeline.measurements.measurement_decoder import decode_lines_to_measurements


class LineFirstParser:
    def parse(self, text: str, *, confidence: float) -> list[AiMeasurement]:
        return self.parse_text(text, confidence=confidence)

    def parse_lines(self, lines: Iterable[str], *, confidence: float) -> list[AiMeasurement]:
        ordered_lines = [line for line in lines if str(line).strip()]
        return decode_lines_to_measurements(ordered_lines, confidence=confidence)

    def parse_text(self, text: str, *, confidence: float) -> list[AiMeasurement]:
        return self.parse_lines(text.splitlines(), confidence=confidence)
