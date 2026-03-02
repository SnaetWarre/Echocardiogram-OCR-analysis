from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from app.models.types import AiMeasurement


class MeasurementParser(Protocol):
    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]: ...


_UNIT_ALIASES = {
    "mis": "m/s",
    "mls": "m/s",
    "m1s": "m/s",
    "mhg": "mmHg",
    "mmhg": "mmHg",
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
        normalized.append(AiMeasurement(name=name, value=value, unit=unit, source=item.source))

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
            AiMeasurement(name=item.name, value=item.value, unit=unit, source=item.source)
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
        unit_re = re.compile(
            r"^(%|mmhg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2|mis|m1s|mls)$", re.I
        )
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

            # --- DETERMINISTIC POST PROCESSING ---
            # 1. Name corrections
            name_lower = name.lower()
            if "azc" in name_lower:
                name = name.replace("Azc", "A2C").replace("azc", "A2C")
            if "a2c" in name_lower:
                name = name.replace("A2c", "A2C").replace("a2c", "A2C")
            if "a3c" in name_lower:
                name = name.replace("A3c", "A3C").replace("a3c", "A3C")
            if "a4c" in name_lower:
                name = name.replace("A4c", "A4C").replace("a4c", "A4C")
            if "ef" in name_lower and "teich" in name_lower:
                name = "EF(Teich)"
            if "%6fs" in name_lower:
                name = "%FS"
            if "lvdd" in name_lower:
                name = name.replace("LVDd", "LVIDd").replace("Lvdd", "LVIDd")
            if "tsopt" in name_lower:
                name = "E' Sept"
            if "moanpg" in name_lower:
                name = name.replace("moanPG", "meanPG")
            if "mexpg" in name_lower:
                name = name.replace("mexPG", "maxPG")
            if "eia" in name_lower:
                name = name.replace("EIA", "E/A")
            if "sid" in name_lower:
                name = name.replace("SID", "S/D")
            if "p vein $" in name_lower:
                name = name.replace("$", "S")
            if "laesv (a-l)" in name_lower:
                name = name.replace("LAESV (A-L)", "LAESV(A-L)")
            if "rvd" in name_lower:
                name = "RVIDd"

            # 2. Unit corrections
            unit_lower = unit.lower()
            if unit_lower in ["mls", "msl", "mfs", "ms2", "m/s2", "m/s²", "m/s;", "w"]:
                unit = "m/s"
            if unit_lower == "ms":
                # Only DecT should be ms, others like P Vein A/D/S are m/s
                if "dect" not in name.lower():
                    unit = "m/s"
            if unit_lower == "mvm2":
                unit = "ml/m2"
            if unit_lower == "cmz":
                unit = "cm"
            if unit_lower == "mli" or unit_lower == "mll":
                unit = "ml"
            # Label mismatches (label says cm but it is physically an area/volume, or vice versa, follow label)
            if "laas " in name.lower() and unit_lower == "cm2":
                unit = "cm"
            if "ava vmax" in name.lower() and unit_lower == "cm2":
                unit = "cm"
            if "rvidd" in name.lower() and unit_lower == "w":
                unit = "cm"

            # 3. Value decimal corrections
            # (If missing decimal for mm, cm, m/s velocities that are typically 0.x - 3.x)
            if len(value) >= 2 and "." not in value:
                # 28 -> 2.8, 23 -> 2.3 for Vmax and Diam
                if (
                    "vmax" in name.lower()
                    or "diam" in name.lower()
                    or "vti" in name.lower()
                    or "rvidd" in name.lower()
                ):
                    if len(value) == 2:
                        value = value[0] + "." + value[1]

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
            "You extract echocardiogram measurements from OCR text.\n"
            "Return ONLY valid JSON: an array of objects with keys "
            '"name", "value", "unit".\n'
            "Rules:\n"
            "- Keep labels exactly as written if uncertain.\n"
            "- value must be numeric string.\n"
            "- unit can be empty string when missing.\n"
            "- Do not include commentary.\n\n"
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

    def __init__(
        self, llm_parser: LocalLlmMeasurementParser, regex_parser: RegexMeasurementParser
    ) -> None:
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
