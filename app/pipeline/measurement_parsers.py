from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

from app.models.types import AiMeasurement


class MeasurementParser(Protocol):
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        ...


_UNIT_ALIASES = {
    "mis": "m/s",
    "mls": "m/s",
    "m1s": "m/s",
    "mhg": "mmHg",
    "mmhg": "mmHg",
    "m/s^2": "m/s2",
}

_COMPOUND_MERGE: Dict[Tuple[str, str], str] = {
    ("tr", "vmax"): "TR Vmax",
    ("tr", "maxpg"): "TR maxPG",
    ("pv", "vmax"): "PV Vmax",
    ("pv", "maxpg"): "PV maxPG",
    ("mv", "vmax"): "MV Vmax",
    ("mv", "maxpg"): "MV maxPG",
    ("av", "vmax"): "AV Vmax",
    ("av", "maxpg"): "AV maxPG",
}

_COMPOUND_PREFIXES = frozenset({"tr", "pv", "mv", "av"})
_COMPOUND_SUFFIXES = frozenset({"vmax", "vmean", "maxpg", "meanpg"})

_EVAL_NAME_ALIASES = {
    "tr maxpg": "TR maxPG",
    "tr vmax": "TR Vmax",
    "pv maxpg": "PV maxPG",
    "pv vmax": "PV Vmax",
    "ef(teich)": "EF(Teich)",
    "ef (teich)": "EF(Teich)",
    "laesv(a-l)": "LAESV (A-L)",
    "laesv (a-l)": "LAESV (A-L)",
    "laesv a-l": "LAESV (A-L)",
    "ao diam": "Ao Diam",
    "ao asc": "Ao asc",
    "arch diam": "Ao arch diam",
    "lvot diam": "LVOT Diam",
    "la diam": "LA Diam",
}

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
    text = " ".join(text.split()).strip()
    if not text:
        return text
    lowered = text.lower()
    if lowered in _EVAL_NAME_ALIASES:
        return _EVAL_NAME_ALIASES[lowered]

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
            base = base[: -5] + "maxPG"
        elif lowered.endswith("meanpg"):
            base = base[: -6] + "meanPG"
        elif lowered.endswith("vmax"):
            base = base[: -4] + "Vmax"
        elif lowered.endswith("vmean"):
            base = base[: -5] + "Vmean"
        elif lowered.endswith("vti"):
            base = base[: -3] + "VTI"
        elif lowered.endswith("dect"):
            base = base[: -4] + "DecT"
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
    return raw.replace(",", ".").strip()


def _normalize_unit(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    unit = raw.strip()
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


def _merge_compound_measurements(items: List[AiMeasurement]) -> List[AiMeasurement]:
    """Merge split compound measurements (e.g. tr + vmax -> TR Vmax) with same value."""
    if len(items) < 2:
        return items
    result: List[AiMeasurement] = []
    used: set = set()
    for i, a in enumerate(items):
        if i in used:
            continue
        val_a = _normalize_value(a.value)
        name_a_lower = a.name.strip().lower()
        merged = None
        for j, b in enumerate(items):
            if j <= i or j in used:
                continue
            if _normalize_value(b.value) != val_a:
                continue
            name_b_lower = b.name.strip().lower()
            pair = None
            if name_a_lower in _COMPOUND_PREFIXES and name_b_lower in _COMPOUND_SUFFIXES:
                pair = (name_a_lower, name_b_lower)
            elif name_b_lower in _COMPOUND_PREFIXES and name_a_lower in _COMPOUND_SUFFIXES:
                pair = (name_b_lower, name_a_lower)
            if pair and pair in _COMPOUND_MERGE:
                merged_unit = (a.unit or b.unit or "").strip() or None
                merged_unit = _normalize_unit(merged_unit) if merged_unit else None
                merged = AiMeasurement(
                    name=_COMPOUND_MERGE[pair],
                    value=val_a,
                    unit=merged_unit,
                    source=a.source,
                )
                used.add(j)
                break
        if merged is not None:
            used.add(i)
            result.append(merged)
        else:
            result.append(a)
    return result


def _is_telemetry_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _TELEMETRY_KEYWORDS)


def _postprocess_measurements(items: List[AiMeasurement]) -> List[AiMeasurement]:
    items = _merge_compound_measurements(items)
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
            AiMeasurement(name=name, value=value, unit=unit, source=item.source)
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
        enriched.append(AiMeasurement(name=item.name, value=item.value, unit=unit, source=item.source))

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


class RegexMeasurementParser:
    _pattern = re.compile(
        r"(?P<name>[A-Za-z][A-Za-z0-9\s/\-()']+?)\s+"
        r"(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)?",
        flags=re.IGNORECASE,
    )

    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        items: List[AiMeasurement] = []
        seen_keys = set()
        for line in text.splitlines():
            match = self._pattern.search(line.strip())
            if not match:
                continue
            name = _normalize_name(match.group("name"))
            value = match.group("value").replace(",", ".")
            unit = _normalize_unit((match.group("unit") or "").strip() or None)
            key = (name.lower(), value, (unit or "").lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            items.append(
                AiMeasurement(
                    name=name,
                    value=value,
                    unit=unit,
                    source=f"regex_parser:{confidence:.2f}",
                )
            )

        # Generic multiline fallback: handles line-split OCR without hardcoded dictionaries.
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        number_re = re.compile(r"[-+]?\d+(?:[.,]\d+)?$")
        unit_re = re.compile(r"^(%|mmhg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2|mis|m1s|mls)$", re.I)
        alpha_re = re.compile(r"[A-Za-z]")
        inline_value_re = re.compile(r"^([-+]?\d+(?:[.,]\d+)?)\s*([A-Za-z/%0-9]+)?$")

        def _is_alpha_token(token: str) -> bool:
            return bool(alpha_re.search(token)) and not number_re.match(token)

        def _clean_token(raw: str) -> str:
            return " ".join(raw.replace("|", " ").replace("_", " ").split())

        def _token_is_plausible_name_part(token: str) -> bool:
            if not re.search(r"[A-Za-z]", token):
                return False
            if len(token) > 20:
                return False
            if len(token.split()) > 2:
                return False
            return bool(re.fullmatch(r"[A-Za-z0-9'()/\-]+(?:\s+[A-Za-z0-9'()/\-]+)?", token))

        def _name_is_plausible(name: str) -> bool:
            parts = name.split()
            if not (1 <= len(parts) <= 4):
                return False
            if len(name) > 28:
                return False
            return any(len(part) <= 6 for part in parts)

        idx = 0
        while idx < len(lines):
            token = _clean_token(lines[idx])
            if not token:
                idx += 1
                continue
            if not _is_alpha_token(token):
                idx += 1
                continue

            # Build name from consecutive alpha tokens until the first numeric token.
            name_parts: List[str] = []
            j = idx
            while j < len(lines):
                part = _clean_token(lines[j])
                if not part:
                    j += 1
                    continue
                if number_re.match(part):
                    break
                if inline_value_re.match(part):
                    break
                if _is_alpha_token(part) and _token_is_plausible_name_part(part):
                    name_parts.append(part)
                    if len(name_parts) >= 4:
                        j += 1
                        break
                    j += 1
                    continue
                break

            if not name_parts:
                idx += 1
                continue

            name = " ".join(name_parts)
            if not _name_is_plausible(name):
                idx += max(1, len(name_parts))
                continue
            value = None
            unit = None
            value_idx = j
            for probe_idx in range(value_idx, min(len(lines), value_idx + 4)):
                candidate = _clean_token(lines[probe_idx]).replace(",", ".").strip()
                if not candidate:
                    continue
                if value is None and number_re.match(candidate):
                    value = candidate
                    if probe_idx + 1 < len(lines):
                        next_u = _clean_token(lines[probe_idx + 1]).strip()
                        if unit_re.match(next_u):
                            unit = _normalize_unit(next_u)
                    break
                # Handle inline value+unit on one line.
                m_inline = inline_value_re.match(candidate)
                if m_inline and value is None:
                    value = m_inline.group(1).replace(",", ".")
                    unit = _normalize_unit((m_inline.group(2) or "").strip() or None)
                    break

            if value is not None:
                key = (name.lower(), value, (unit or "").lower())
                if key not in seen_keys:
                    seen_keys.add(key)
                    items.append(
                        AiMeasurement(
                            name=name,
                            value=value,
                            unit=unit,
                            source=f"regex_multiline:{confidence:.2f}",
                        )
                    )
            idx = max(j, idx + 1)
        return _postprocess_measurements(items)


@dataclass
class LocalLlmParserConfig:
    model: str = "qwen2.5:7b-instruct-q4_K_M"
    command: str = "ollama"
    timeout_s: float = 30.0


class LocalLlmMeasurementParser:
    """
    Local parser using an on-device LLM CLI (default: ollama).
    It converts noisy OCR text into structured measurements JSON.
    """

    def __init__(self, config: Optional[LocalLlmParserConfig] = None) -> None:
        self.config = config or LocalLlmParserConfig()

    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        if not text.strip():
            return []
        prompt = self._build_prompt(text)
        try:
            payload = self._run_model(prompt)
        except Exception:
            return []
        parsed = self._parse_json_payload(payload)
        items: List[AiMeasurement] = []
        for row in parsed:
            name = str(row.get("name", "")).strip()
            value = str(row.get("value", "")).strip().replace(",", ".")
            unit = str(row.get("unit", "")).strip()
            if not name or not value:
                continue
            items.append(
                AiMeasurement(
                    name=name,
                    value=value,
                    unit=unit or None,
                    source=f"local_llm:{self.config.model}:{confidence:.2f}",
                )
            )
        return _postprocess_measurements(items)

    def _build_prompt(self, ocr_text: str) -> str:
        if self._is_nuextract_model():
            return self._build_nuextract_prompt(ocr_text)
        return self._build_generic_json_prompt(ocr_text)

    def _is_nuextract_model(self) -> bool:
        return "nuextract" in self.config.model.lower()

    def _build_generic_json_prompt(self, ocr_text: str) -> str:
        return (
            "You extract echocardiogram measurements from OCR text. "
            "Return ONLY valid JSON: an array of objects with keys \"name\", \"value\", \"unit\".\n\n"
            "Examples (match these exact label formats):\n"
            "- \"TR Vmax 1.9 m/s  TR maxPG 14 mmHg\" -> "
            "[{\"name\": \"TR Vmax\", \"value\": \"1.9\", \"unit\": \"m/s\"}, "
            "{\"name\": \"TR maxPG\", \"value\": \"14\", \"unit\": \"mmHg\"}]\n"
            "- \"IVSd 0.9  LVIDd 5.4  LVPWd 1.0 cm\" -> "
            "[{\"name\": \"IVSd\", \"value\": \"0.9\", \"unit\": \"cm\"}, "
            "{\"name\": \"LVIDd\", \"value\": \"5.4\", \"unit\": \"cm\"}, "
            "{\"name\": \"LVPWd\", \"value\": \"1.0\", \"unit\": \"cm\"}]\n"
            "- \"LVIDs 3.6cm  EF(Teich) 62%  %FS 34\" -> "
            "[{\"name\": \"LVIDs\", \"value\": \"3.6\", \"unit\": \"cm\"}, "
            "{\"name\": \"EF(Teich)\", \"value\": \"62\", \"unit\": \"%\"}, "
            "{\"name\": \"%FS\", \"value\": \"34\", \"unit\": \"%\"}]\n"
            "- \"RA LENGTH 5.9  LA LENGTH 6.6 cm\" -> "
            "[{\"name\": \"RA LENGTH\", \"value\": \"5.9\", \"unit\": \"cm\"}, "
            "{\"name\": \"LA LENGTH\", \"value\": \"6.6\", \"unit\": \"cm\"}]\n"
            "- \"MV E VEL 0.7  MV DecT 183 ms  MV A Vel 0.6 m/s  MV E/A Ratio 1.2\" -> "
            "[{\"name\": \"MV E VEL\", \"value\": \"0.7\", \"unit\": \"m/s\"}, "
            "{\"name\": \"MV DecT\", \"value\": \"183\", \"unit\": \"ms\"}, "
            "{\"name\": \"MV A Vel\", \"value\": \"0.6\", \"unit\": \"m/s\"}, "
            "{\"name\": \"MV E/A Ratio\", \"value\": \"1.2\", \"unit\": \"\"}]\n"
            "- \"P Vein A 0.3  P vein D 0.4  P Vein S 0.5 m/s  P Vein S/D Ratio 1.2\" -> "
            "[{\"name\": \"P Vein A\", \"value\": \"0.3\", \"unit\": \"m/s\"}, "
            "{\"name\": \"P vein D\", \"value\": \"0.4\", \"unit\": \"m/s\"}, "
            "{\"name\": \"P Vein S\", \"value\": \"0.5\", \"unit\": \"m/s\"}, "
            "{\"name\": \"P Vein S/D Ratio\", \"value\": \"1.2\", \"unit\": \"\"}]\n"
            "- \"LALs A4C 5.8  LAAs A4C 19.5 cm2  LAESV A-L A4C 56 ml\" -> "
            "[{\"name\": \"LALs A4C\", \"value\": \"5.8\", \"unit\": \"cm\"}, "
            "{\"name\": \"LAAs A4C\", \"value\": \"19.5\", \"unit\": \"cm2\"}, "
            "{\"name\": \"LAESV A-L A4C\", \"value\": \"56\", \"unit\": \"ml\"}]\n"
            "- \"E' Lat 0.09  E' Sept 0.08 m/s\" -> "
            "[{\"name\": \"E' Lat\", \"value\": \"0.09\", \"unit\": \"m/s\"}, "
            "{\"name\": \"E' Sept\", \"value\": \"0.08\", \"unit\": \"m/s\"}]\n"
            "- \"LVOT Vmax 1.1 m/s  LVOT maxPG 5 mmHg  LVOT VTI 19.9 cm\" -> "
            "[{\"name\": \"LVOT Vmax\", \"value\": \"1.1\", \"unit\": \"m/s\"}, "
            "{\"name\": \"LVOT maxPG\", \"value\": \"5\", \"unit\": \"mmHg\"}, "
            "{\"name\": \"LVOT VTI\", \"value\": \"19.9\", \"unit\": \"cm\"}]\n"
            "- \"AVA Vmax 2.8  AVA (VTI) 2.3 cm2  AV Vmax 1.3 m/s  AV maxPG 6 mmHg\" -> "
            "[{\"name\": \"AVA Vmax\", \"value\": \"2.8\", \"unit\": \"cm2\"}, "
            "{\"name\": \"AVA (VTI)\", \"value\": \"2.3\", \"unit\": \"cm2\"}, "
            "{\"name\": \"AV Vmax\", \"value\": \"1.3\", \"unit\": \"m/s\"}, "
            "{\"name\": \"AV maxPG\", \"value\": \"6\", \"unit\": \"mmHg\"}]\n"
            "- \"Ao Desc Diam 2.6  Ao Arch Diam 2.8 cm\" -> "
            "[{\"name\": \"Ao Desc Diam\", \"value\": \"2.6\", \"unit\": \"cm\"}, "
            "{\"name\": \"Ao Arch Diam\", \"value\": \"2.8\", \"unit\": \"cm\"}]\n"
            "- \"IVC 2.2  RVIDd 3.2 cm\" -> "
            "[{\"name\": \"IVC\", \"value\": \"2.2\", \"unit\": \"cm\"}, "
            "{\"name\": \"RVIDd\", \"value\": \"3.2\", \"unit\": \"cm\"}]\n"
            "- \"EF Biplane 64%  LVEDV MOD BP 102  LVESV MOD BP 37 ml  SV MOD A2C 58.10 ml\" -> "
            "[{\"name\": \"EF Biplane\", \"value\": \"64\", \"unit\": \"%\"}, "
            "{\"name\": \"LVEDV MOD BP\", \"value\": \"102\", \"unit\": \"ml\"}, "
            "{\"name\": \"LVESV MOD BP\", \"value\": \"37\", \"unit\": \"ml\"}, "
            "{\"name\": \"SV MOD A2C\", \"value\": \"58.10\", \"unit\": \"ml\"}]\n\n"
            "Rules:\n"
            "- Use EXACT label names from examples: IVSd, LVIDd, LVPWd, LVIDs, EF(Teich), %FS, RA/LA LENGTH, MV E VEL, MV DecT (ms), P Vein A/D/S, LALs/LAAs/LAESV A4C, E' Lat/Sept, LVOT/AV/AVA, Ao Desc/Arch Diam, IVC, RVIDd, EF Biplane, SV MOD.\n"
            "- ALWAYS include full name. Never output just \"Vmax\" or \"diam\". Include method/view: mod, A4C, A2C, A3C, BP, (A-L).\n"
            "- Units: m/s (velocity), mmHg (pressure), cm (dimensions), cm2 (area), ml (volume), % (EF/FS), ms (DecT only).\n"
            "- Infer missing units from context. value = numeric string. unit = \"\" when unknown.\n"
            "- JSON only. No commentary.\n\n"
            "OCR text:\n"
            f"{ocr_text}\n"
        )

    def _build_nuextract_prompt(self, ocr_text: str) -> str:
        return (
            "### Template:\n"
            "{\n"
            '  "measurements": [\n'
            "    {\n"
            '      "name": "",\n'
            '      "value": "",\n'
            '      "unit": ""\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "### Example:\n"
            "{\n"
            '  "measurements": [\n'
            '    {"name": "PV Vmax", "value": "0.87", "unit": "m/s"},\n'
            '    {"name": "PV maxPG", "value": "3", "unit": "mmHg"}\n'
            "  ]\n"
            "}\n"
            "### Text:\n"
            f"{ocr_text}\n"
        )

    def _run_model(self, prompt: str) -> str:
        cmd = [
            self.config.command,
            "run",
            self.config.model,
            prompt,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Local LLM parser failed ({self.config.command}): {(proc.stderr or proc.stdout).strip()}"
            )
        return (proc.stdout or "").strip()

    def _parse_json_payload(self, payload: str) -> List[Dict[str, object]]:
        payload = payload.strip()
        if not payload:
            return []
        json_blob = self._extract_json(payload)
        try:
            parsed = json.loads(json_blob)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            measurements = parsed.get("measurements")
            if isinstance(measurements, list):
                return [row for row in measurements if isinstance(row, dict)]
            return []
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
        return []

    @staticmethod
    def _extract_json(payload: str) -> str:
        array_start = payload.find("[")
        array_end = payload.rfind("]")
        if array_start != -1 and array_end != -1 and array_end > array_start:
            return payload[array_start : array_end + 1]
        obj_start = payload.find("{")
        obj_end = payload.rfind("}")
        if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
            return payload[obj_start : obj_end + 1]
        return "[]"


class HybridMeasurementParser:
    """
    Prefer local LLM parsing and fall back to regex on model failures.
    """

    def __init__(self, llm_parser: LocalLlmMeasurementParser, regex_parser: RegexMeasurementParser) -> None:
        self.llm_parser = llm_parser
        self.regex_parser = regex_parser

    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        try:
            llm_items = self.llm_parser.parse(text, confidence=confidence)
        except Exception:
            llm_items = []
        if llm_items:
            return llm_items
        return self.regex_parser.parse(text, confidence=confidence)


def build_parser(mode: str, parameters: Optional[Dict[str, object]] = None) -> MeasurementParser:
    params = parameters or {}
    parser_mode = (mode or "regex").strip().lower()
    regex_parser = RegexMeasurementParser()
    if parser_mode == "regex":
        return regex_parser

    llm_model = str(params.get("llm_model", "qwen2.5:7b-instruct-q4_K_M"))
    llm_command = str(params.get("llm_command", "ollama"))
    llm_timeout_s = float(params.get("llm_timeout_s", 30.0))
    llm_parser = LocalLlmMeasurementParser(
        config=LocalLlmParserConfig(
            model=llm_model,
            command=llm_command,
            timeout_s=llm_timeout_s,
        )
    )
    if parser_mode == "local_llm":
        return llm_parser
    if parser_mode == "hybrid":
        return HybridMeasurementParser(llm_parser=llm_parser, regex_parser=regex_parser)
    raise ValueError(f"Unsupported parser mode: {mode}")
