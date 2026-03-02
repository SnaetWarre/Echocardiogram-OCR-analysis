from __future__ import annotations

import re
from typing import Dict, List, Optional, Protocol

from app.models.types import AiMeasurement


class MeasurementParser(Protocol):
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        ...


_UNIT_ALIASES: Dict[str, str] = {
    "mmhg": "mmHg",
    "mhg": "mmHg",
    "mis": "m/s",
    "m1s": "m/s",
    "mls": "m/s",
}

_MEASUREMENT_RE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9\s/\-()']+?)\s+"
    r"(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)?",
    flags=re.IGNORECASE,
)


def _normalize_name(raw: str) -> str:
    cleaned = raw.replace("|", " ").replace("_", " ").replace("¥", "V").replace("’", "'")
    return " ".join(cleaned.split()).strip()


def _normalize_unit(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    unit = raw.strip()
    if not unit:
        return None
    return _UNIT_ALIASES.get(unit.lower(), unit)


class RegexMeasurementParser:
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        measurements: List[AiMeasurement] = []
        seen: set[tuple[str, str, str]] = set()
        for line in text.splitlines():
            match = _MEASUREMENT_RE.search(line.strip())
            if match is None:
                continue
            name = _normalize_name(match.group("name"))
            value = match.group("value").replace(",", ".")
            unit = _normalize_unit((match.group("unit") or "").strip() or None)
            if not name:
                continue
            key = (name.lower(), value, (unit or "").lower())
            if key in seen:
                continue
            seen.add(key)
            measurements.append(
                AiMeasurement(
                    name=name,
                    value=value,
                    unit=unit,
                    source=f"regex:{confidence:.2f}",
                )
            )
        return measurements


def build_parser(mode: str, parameters: Optional[Dict[str, object]] = None) -> MeasurementParser:
    _ = (mode, parameters)
    return RegexMeasurementParser()
