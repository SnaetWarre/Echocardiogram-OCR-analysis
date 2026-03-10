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
    "m/s;": "m/s",
    "m/s.": "m/s",
    "m/s,": "m/s",
    "mmhg,": "mmHg",
    "mmhg.": "mmHg",
}

_LATEX_NOISE_RE = re.compile(r"\\(?:text|mathrm)\{([^}]*)\}")
_LATEX_SPACING_RE = re.compile(r"\\[,;! ]")
_COMPACT_VALUE_UNIT_RE = re.compile(
    r"(?P<value>[-+]?\d+(?:[.,]\d+)?)(?P<unit>%|mmHg|ml/m2|m/s2|cm2|cm/s|m/s|bpm|cm|mm|ms|ml|s)\b",
    re.IGNORECASE,
)
_INDEXED_NAME_RE = re.compile(
    r"^(?P<prefix>\d{1,2})\s+(?P<label>[A-Za-z%][A-Za-z0-9\s/\-()']*)$"
)
_VALUE_ONLY_RE = re.compile(
    r"^(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>%|mmHg|ml/m2|m/s2|cm2|cm/s|m/s|bpm|cm|mm|ms|ml|s|mis|m1s|mls)?$",
    re.IGNORECASE,
)

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


class RegexMeasurementParser:
    _pattern = re.compile(
        r"(?P<name>[A-Za-z0-9%][A-Za-z0-9\s/\-()']+?)\s+"
        r"(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>%|mmHg|ml/m2|m/s2|cm2|cm/s|m/s|bpm|cm|mm|ms|ml|s)?",
        flags=re.IGNORECASE,
    )

    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        items: List[AiMeasurement] = []
        seen_keys = set()

        def _clean_ocr_text(raw: str) -> str:
            cleaned = _LATEX_NOISE_RE.sub(r"\1", raw)
            cleaned = _LATEX_SPACING_RE.sub(" ", cleaned)
            cleaned = cleaned.replace("{", " ").replace("}", " ").replace("\\", " ")
            cleaned = _COMPACT_VALUE_UNIT_RE.sub(r"\g<value> \g<unit>", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned)
            cleaned = cleaned.replace(" \n", "\n").replace("\n ", "\n")
            return cleaned.strip()

        def _clean_line(raw: str) -> str:
            line = _clean_ocr_text(raw)
            line = line.replace("|", " ").replace("_", " ")
            line = re.sub(r"\s+", " ", line)
            return line.strip()

        def _extract_label_prefix(line: str) -> tuple[str | None, str]:
            cleaned = _clean_line(line)
            match = _INDEXED_NAME_RE.match(cleaned)
            if match:
                return match.group("prefix"), match.group("label").strip()
            return None, cleaned

        def _is_value_only_line(line: str) -> tuple[str, str | None] | None:
            cleaned = _clean_line(line)
            match = _VALUE_ONLY_RE.match(cleaned)
            if match is None:
                return None
            value = _normalize_value(match.group("value"))
            unit = _normalize_unit(match.group("unit"))
            if not value:
                return None
            return value, unit

        def _add_item(name: str, value: str, unit: str | None, source: str) -> None:
            normalized_name = _normalize_name(name)
            normalized_value = _normalize_value(value)
            normalized_unit = _normalize_unit(unit)
            key = (normalized_name.lower(), normalized_value, (normalized_unit or "").lower())
            if key in seen_keys:
                return
            seen_keys.add(key)
            items.append(
                AiMeasurement(
                    name=normalized_name,
                    value=normalized_value,
                    unit=normalized_unit,
                    source=source,
                    order_hint=len(items),
                )
            )

        cleaned_text = "\n".join(_clean_line(line) for line in text.splitlines() if _clean_line(line))
        for line in cleaned_text.splitlines():
            for match in self._pattern.finditer(line.strip()):
                _add_item(
                    match.group("name"),
                    match.group("value"),
                    (match.group("unit") or "").strip() or None,
                    f"regex_parser:{confidence:.2f}",
                )

        # Reassemble split OCR lines such as:
        #   "1 IVSd"
        #   "0.9 cm"
        # into:
        #   "1 IVSd 0.9 cm"
        lines = [line for line in cleaned_text.splitlines() if line.strip()]
        idx = 0
        while idx < len(lines):
            prefix, label = _extract_label_prefix(lines[idx])
            value_only = _is_value_only_line(lines[idx])

            if value_only is None and re.search(r"[A-Za-z%]", label):
                if idx + 1 < len(lines):
                    next_value = _is_value_only_line(lines[idx + 1])
                    if next_value is not None:
                        value, unit = next_value
                        merged_name = f"{prefix} {label}".strip() if prefix else label
                        _add_item(
                            merged_name,
                            value,
                            unit,
                            f"regex_reassembled:{confidence:.2f}",
                        )
                        idx += 2
                        continue

                if idx + 2 < len(lines):
                    next_prefix, next_label = _extract_label_prefix(lines[idx + 1])
                    next_next_value = _is_value_only_line(lines[idx + 2])
                    if (
                        next_next_value is not None
                        and re.search(r"[A-Za-z%]", next_label)
                        and prefix is None
                    ):
                        merged_name = f"{label} {next_label}".strip()
                        value, unit = next_next_value
                        if next_prefix:
                            merged_name = f"{next_prefix} {merged_name}".strip()
                        _add_item(
                            merged_name,
                            value,
                            unit,
                            f"regex_reassembled:{confidence:.2f}",
                        )
                        idx += 3
                        continue

            idx += 1

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
                    order_hint=len(items),
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
            "- Keep labels exactly as written if uncertain, including a real leading row number like 1 or 2 when it belongs to the measurement label.\n"
            "- Measurements may be split across adjacent OCR lines; merge them into one final measurement.\n"
            "- If one line is mostly a label and the next line is mostly a value/unit, combine them.\n"
            "- Ignore non-measurement UI noise, decorative symbols, and telemetry.\n"
            "- Normalize units to canonical forms when obvious: m/s, mmHg, cm, mm, ms, %, ml, ml/m2, cm2, bpm, m/s2.\n"
            "- value must be numeric string only.\n"
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


class RegexThenLlmMeasurementParser:
    """
    Prefer fast regex parsing and only call the local LLM if regex finds nothing.
    Useful for human-in-the-loop review where speed matters more than squeezing out
    the absolute best parser score on every file.
    """

    def __init__(self, regex_parser: RegexMeasurementParser, llm_parser: MeasurementParser) -> None:
        self.regex_parser = regex_parser
        self.llm_parser = llm_parser

    def parse(self, text: str, *, confidence: float) -> List[AiMeasurement]:
        regex_items = self.regex_parser.parse(text, confidence=confidence)
        if regex_items:
            return regex_items
        try:
            return self.llm_parser.parse(text, confidence=confidence)
        except Exception:
            return []


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
    if parser_mode in {"regex_then_llm", "fast_hybrid"}:
        return RegexThenLlmMeasurementParser(regex_parser=regex_parser, llm_parser=llm_parser)
    raise ValueError(f"Unsupported parser mode: {mode}")
