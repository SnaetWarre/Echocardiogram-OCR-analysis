from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.types import AiMeasurement
from app.pipeline.measurement_decoder import decode_lines_to_measurements
from app.pipeline.measurement_parsers import MeasurementParser


@dataclass
class LineFirstParser:
    fallback_parser: MeasurementParser | None = None

    def parse_lines(self, lines: Iterable[str], *, confidence: float) -> list[AiMeasurement]:
        ordered_lines = [line for line in lines if str(line).strip()]
        measurements = decode_lines_to_measurements(ordered_lines, confidence=confidence)
        if measurements:
            return measurements
        if self.fallback_parser is None:
            return []
        return self.fallback_parser.parse("\n".join(ordered_lines), confidence=confidence)

    def parse_text(self, text: str, *, confidence: float) -> list[AiMeasurement]:
        return self.parse_lines(text.splitlines(), confidence=confidence)
