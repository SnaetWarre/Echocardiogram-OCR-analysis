from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Dict, List, Protocol, cast

from app.models.types import AiMeasurement


class MeasurementParser(Protocol):
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]: ...


class NoopMeasurementParser:
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        _ = text
        _ = confidence
        return []


_UNIT_ALIASES = {
    "mis": "m/s",
    "mls": "m/s",
    "m1s": "m/s",
    "mhg": "mmHg",
    "mmhg": "mmHg",
    "m/s;": "m/s",
    "m/s.": "m/s",
    "m/s,": "m/s",
    "mmhg,": "mmHg",
    "mmhg.": "mmHg",
}

_LATEX_NOISE_RE = re.compile(r"\\(?:text|mathrm)\{([^}]*)\}")
_LATEX_SPACING_RE = re.compile(r"\\[,;! ]")

_TELEMETRY_KEYWORDS = {
    "fps",
    "mhz",
    "hz",
    "frequency",
    "frame",
    "gain",
    "depth",
    "diastole",
    "systole",
}

_TELEMETRY_UNITS = {"mhz", "hz", "fps"}

_VELOCITY_HINT_RE = re.compile(r"(vmax|vmean|\bvel\b|e')", re.IGNORECASE)
_PG_HINT_RE = re.compile(r"(?:^|\s)(pg|maxpg|meanpg)\b", re.IGNORECASE)


def _normalize_name(raw: str) -> str:
    text = raw.replace("|", " ").replace("_", " ").replace("¥", "V").replace("’", "'")
    text = _LATEX_NOISE_RE.sub(r"\1", text)
    text = _LATEX_SPACING_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ").replace("\\", " ")
    text = " ".join(text.split()).strip()
    if not text:
        return text

    # Keep separators readable and stable for downstream matching.
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\(\s*", "(", text)
    text = re.sub(r"\s*\)", ")", text)

    # Insert spacing around bracketed suffixes (e.g. index(a-l) -> index (a-l)).
    text = re.sub(r"([A-Za-z0-9])\(", r"\1 (", text)

    # Token-level cleanup with conservative capitalization.
    tokens = text.split()
    out: List[str] = []
    for token in tokens:
        base = token
        suffix = ""
        if token.endswith((")", ",", ".", ";", ":")):
            base = token[:-1]
            suffix = token[-1]

        # Normalize common mixed-case measurement suffixes without relying on a fixed dictionary.
        # Examples: vmax/vMax/VMAX -> Vmax, meanpg -> meanPG, dect -> DecT.
        lowered = base.lower()
        compact = re.fullmatch(r"([A-Za-z]{2,4})(maxpg|meanpg|vmax|vmean|vti|dect)", lowered)
        if compact and compact.group(1).isalpha():
            prefix = compact.group(1).upper()
            suffix_map = {
                "maxpg": "maxPG",
                "meanpg": "meanPG",
                "vmax": "Vmax",
                "vmean": "Vmean",
                "vti": "VTI",
                "dect": "DecT",
            }
            out.append(f"{prefix} {suffix_map[compact.group(2)]}" + suffix)
            continue
        if lowered.endswith("maxpg"):
            base = base[:-5] + "maxPG"
        elif lowered.endswith("meanpg"):
            base = base[:-6] + "meanPG"
        elif lowered.endswith("vmax"):
            base = base[:-4] + "Vmax"
        elif lowered.endswith("vmean"):
            base = base[:-5] + "Vmean"
        elif lowered.endswith("vti"):
            base = base[:-3] + "VTI"
        elif lowered.endswith("dect"):
            base = base[:-4] + "DecT"
        elif lowered in {"ef", "fs", "ivc", "ivsd", "lvidd", "lvids", "lvpwd", "rvidd"}:
            base = lowered.upper()
        elif re.fullmatch(r"[A-Za-z]{2,4}", base) and base.upper() == base:
            base = base.upper()
        elif re.fullmatch(r"[a-z]{1,4}", base):
            base = base.lower()

        out.append(base + suffix)

    text = " ".join(out)

    # Normalize bracket content case for abbreviations: (a-l) -> (A-L)
    text = re.sub(r"\(([a-z]-[a-z])\)", lambda m: f"({m.group(1).upper()})", text)
    # Canonicalize AVPG variants to standard pressure-gradient labels.
    text = re.sub(r"\bAVPG\s*\(\s*mean\s*\)", "AV meanPG", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAVPG\b", "AV maxPG", text, flags=re.IGNORECASE)
    return text.strip()


def _normalize_value(raw: str) -> str:
    text = _LATEX_NOISE_RE.sub(r"\1", raw)
    text = _LATEX_SPACING_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ").replace("\\", " ")
    return text.replace(",", ".").strip()


def _normalize_unit(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    unit = _LATEX_NOISE_RE.sub(r"\1", raw)
    unit = _LATEX_SPACING_RE.sub(" ", unit)
    unit = unit.replace("{", " ").replace("}", " ").replace("\\", " ")
    unit = unit.strip()
    if not unit:
        return None
    lowered = unit.lower()
    if lowered in _UNIT_ALIASES:
        return _UNIT_ALIASES[lowered]
    return unit


def _complete_unit(name: str, unit: Optional[str]) -> Optional[str]:
    lowered_unit = (unit or "").lower()
    has_velocity_hint = bool(_VELOCITY_HINT_RE.search(name))
    has_pg_hint = bool(_PG_HINT_RE.search(name))

    if has_velocity_hint and (not lowered_unit or lowered_unit == "ms"):
        return "m/s"
    if has_pg_hint and not lowered_unit:
        return "mmHg"
    return unit


def _name_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", raw.lower())


def _is_telemetry_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _TELEMETRY_KEYWORDS)


def _postprocess_measurements(items: List[AiMeasurement]) -> List[AiMeasurement]:
    normalized: List[AiMeasurement] = []
    for item in items:
        name = _normalize_name(item.name)
        value = _normalize_value(item.value)
        unit = _normalize_unit(item.unit)
        if not name or not value:
            continue
        if not re.search(r"[A-Za-z]", name):
            continue
        if _is_telemetry_name(name):
            continue
        if unit and unit.lower() in _TELEMETRY_UNITS:
            continue
        if not re.match(r"^[-+]?\d+(?:\.\d+)?$", value):
            continue
        unit = _complete_unit(name, unit)
        normalized.append(
            AiMeasurement(
                name=name,
                value=value,
                unit=unit,
                source=item.source,
                order_hint=item.order_hint,
                raw_ocr_text=item.raw_ocr_text,
                corrected_value=item.corrected_value,
                flags=list(item.flags or []),
            )
        )

    # Conservative unit completion: same semantic label + value gets unit from any duplicate.
    best_unit_by_key: Dict[str, str] = {}
    for item in normalized:
        if item.unit:
            key = f"{_name_key(item.name)}|{item.value}"
            best_unit_by_key[key] = item.unit

    enriched: List[AiMeasurement] = []
    for item in normalized:
        unit = item.unit
        if not unit:
            key = f"{_name_key(item.name)}|{item.value}"
            unit = best_unit_by_key.get(key)
        enriched.append(
            AiMeasurement(
                name=item.name,
                value=item.value,
                unit=unit,
                source=item.source,
                order_hint=item.order_hint,
                raw_ocr_text=item.raw_ocr_text,
                corrected_value=item.corrected_value,
                flags=list(item.flags or []),
            )
        )

    # Deduplicate near-identical variants; keep longest label and filled unit.
    dedup: Dict[str, AiMeasurement] = {}
    for item in enriched:
        key = f"{_name_key(item.name)}|{item.value}|{(item.unit or '').lower()}"
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = item
            continue
        keep = existing
        if len(item.name) > len(existing.name):
            keep = item
        if (existing.unit is None or existing.unit == "") and item.unit:
            keep = item
        dedup[key] = keep
    return list(dedup.values())


def postprocess_measurements(items: List[AiMeasurement]) -> List[AiMeasurement]:
    return _postprocess_measurements(items)


def extract_json_payload(payload: str) -> str:
    payload = payload.strip()
    if not payload:
        return "[]"
    array_start = payload.find("[")
    array_end = payload.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        return payload[array_start : array_end + 1]
    obj_start = payload.find("{")
    obj_end = payload.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        return payload[obj_start : obj_end + 1]
    return "[]"


def parse_json_payload(payload: str) -> Any:
    payload = payload.strip()
    if not payload:
        return []
    try:
        return json.loads(extract_json_payload(payload))
    except json.JSONDecodeError:
        return []


def parse_json_rows(payload: str) -> List[Dict[str, object]]:
    parsed: object = parse_json_payload(payload)
    if isinstance(parsed, dict):
        parsed_dict = cast(Dict[str, object], parsed)
        measurements = parsed_dict["measurements"] if "measurements" in parsed_dict else None
        if isinstance(measurements, list):
            measurement_rows = cast(List[object], measurements)
            rows: List[Dict[str, object]] = []
            for row in measurement_rows:
                if isinstance(row, dict):
                    rows.append(cast(Dict[str, object], row))
            return rows
        return []
    if isinstance(parsed, list):
        parsed_list = cast(List[object], parsed)
        rows: List[Dict[str, object]] = []
        for row in parsed_list:
            if isinstance(row, dict):
                rows.append(cast(Dict[str, object], row))
        return rows
    return []


def run_local_model(*, command: str, model: str, prompt: str, timeout_s: float) -> str:
    cmd = [command, "run", model, prompt]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Local model failed ({command}): {(proc.stderr or proc.stdout).strip()}")
    return (proc.stdout or "").strip()
