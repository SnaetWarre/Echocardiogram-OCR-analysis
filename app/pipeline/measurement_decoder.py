from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.types import AiMeasurement


KNOWN_UNITS = (
    "%",
    "mmHg",
    "ml/m2",
    "m/s2",
    "cm2",
    "cm/s",
    "m/s",
    "bpm",
    "cm",
    "mm",
    "ms",
    "ml",
    "s",
)

_KNOWN_UNIT_ALIASES = {
    "mis": "m/s",
    "mls": "m/s",
    "m1s": "m/s",
    "m/": "m/s",
    "mmha": "mmHg",
    "més": "m/s",
    "mhg": "mmHg",
    "mmhg": "mmHg",
    "em": "cm",
}
_UNIT_TOKEN_PATTERN = "|".join(
    re.escape(token)
    for token in sorted({*KNOWN_UNITS, *_KNOWN_UNIT_ALIASES.keys()}, key=len, reverse=True)
)
_TEXT_TRANSLATION = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        "•": " ",
        "·": " ",
        "→": " ",
        "~": " ",
        "¥": "V",
        "¢": "c",
    }
)
_LATEX_NOISE_RE = re.compile(r"\\(?:text|mathrm)\{([^}]*)\}")
_LATEX_SPACING_RE = re.compile(r"\\[,;! ]")
_COMPACT_VALUE_UNIT_RE = re.compile(
    rf"(?P<value>[-+]?\d+(?:[.,]\d+)?)(?P<unit>{_UNIT_TOKEN_PATTERN})(?=\s|$)",
    flags=re.IGNORECASE,
)
_SLASH_WRAPPED_VALUE_UNIT_RE = re.compile(
    rf"/\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_TOKEN_PATTERN})\s*/",
    flags=re.IGNORECASE,
)
_VALUE_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_PREFIX_RE = re.compile(r"^(?P<prefix>\d{1,2})\s+(?P<body>.+)$")
_VALUE_ONLY_RE = re.compile(
    rf"^(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_TOKEN_PATTERN})?$",
    flags=re.IGNORECASE,
)
_LABEL_REPAIRS = (
    (re.compile(r"\bAVS\b", flags=re.IGNORECASE), "AVA"),
    (re.compile(r"\bL[YV]IDd\b", flags=re.IGNORECASE), "LVIDd"),
    (re.compile(r"\bL[VY](?:I|YI)DS\b", flags=re.IGNORECASE), "LVIDs"),
    (re.compile(r"\bL[YV]P(?:W|VW)d\b", flags=re.IGNORECASE), "LVPWd"),
    (re.compile(r"\bL[YV][YV]P(?:W|VW)d\b", flags=re.IGNORECASE), "LVPWd"),
    (re.compile(r"\bL[VY]P[VW]{2,}d\b", flags=re.IGNORECASE), "LVPWd"),
    (re.compile(r"\bI[VY]Sd\b", flags=re.IGNORECASE), "IVSd"),
    (re.compile(r"\bLALS\b", flags=re.IGNORECASE), "LALs"),
    (re.compile(r"\bLALS\s+AdU\b", flags=re.IGNORECASE), "LALs A4C"),
    (re.compile(r"\bLALS\s+A&v\b", flags=re.IGNORECASE), "LALs A4C"),
    (re.compile(r"\bL[YV]OT\b", flags=re.IGNORECASE), "LVOT"),
    (re.compile(r"\bA[o0]\b", flags=re.IGNORECASE), "Ao"),
    (re.compile(r"\bA20\b", flags=re.IGNORECASE), "A2C"),
    (re.compile(r"\bA40\b", flags=re.IGNORECASE), "A4C"),
    (re.compile(r"\bLAAS\b", flags=re.IGNORECASE), "LAAs"),
    (re.compile(r"\bPRand\s+PG\b", flags=re.IGNORECASE), "PRend PG"),
    (re.compile(r"\b1E['’]?\b", flags=re.IGNORECASE), "1 E'"),
    (re.compile(r"\bE['’]?\s*Lat\b", flags=re.IGNORECASE), "E' Lat"),
    (re.compile(r"\bE['’]?\s*Sept\b", flags=re.IGNORECASE), "E' Sept"),
    (re.compile(r"\bMV\s+Dect\b", flags=re.IGNORECASE), "MV DecT"),
    (re.compile(r"\(eich\s+\d*\s*", flags=re.IGNORECASE), "EF (Teich) "),
    (re.compile(r"\bP\s+Vein\s+s\b", flags=re.IGNORECASE), "P Vein S"),
)
_TRAILING_FILLER_RE = re.compile(r"(?:\s*(?:_+|(?:[.-]\s*){3,}|-+))+\s*$")
_LEADING_PREFIX_GLYPH_RE = re.compile(r"^(?:ı|I|l)\s+(?=[A-Za-z])")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = normalize_space(value).replace(",", ".")
    return cleaned or None


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = normalize_space(unit)
    if not cleaned:
        return None
    alias = _KNOWN_UNIT_ALIASES.get(cleaned.lower())
    if alias is not None:
        return alias
    for known in KNOWN_UNITS:
        if cleaned.lower() == known.lower():
            return known
    return cleaned


def canonicalize_exact_line(text: str) -> str:
    line = _LATEX_NOISE_RE.sub(r"\1", text or "")
    line = line.translate(_TEXT_TRANSLATION)
    line = _LATEX_SPACING_RE.sub(" ", line)
    line = line.replace("{", " ").replace("}", " ")
    line = line.replace("\\%", " %")
    line = line.replace("\\,", " ")
    line = line.replace("|", " ")
    line = _SLASH_WRAPPED_VALUE_UNIT_RE.sub(r"\g<value> \g<unit>", line)
    line = _LEADING_PREFIX_GLYPH_RE.sub("1 ", line)
    line = line.replace("EF(", "EF (")
    line = re.sub(r"^(\d{1,2})(?=[A-Za-z'])", r"\1 ", line)
    line = _COMPACT_VALUE_UNIT_RE.sub(r"\g<value> \g<unit>", line)
    line = normalize_space(line)
    for pattern, replacement in _LABEL_REPAIRS:
        line = pattern.sub(replacement, line)
    line = _strip_known_unit_filler(line)
    line = _TRAILING_FILLER_RE.sub("", line)
    parts = line.split()
    if parts:
        normalized_parts = [normalize_unit(part) or part for part in parts]
        line = " ".join(normalized_parts)
    line = normalize_space(line)
    return "" if _looks_like_symbol_junk(line) else line


_CJK_OR_GARBLE_RE = re.compile(r"[\u4e00-\u9fff\u0400-\u04ff]|\\mathbf|\\text|\\Delta")


def _looks_like_symbol_junk(text: str) -> bool:
    if not text:
        return True
    if _CJK_OR_GARBLE_RE.search(text):
        return True
    alnum_count = sum(1 for char in text if char.isalnum())
    punctuation_count = sum(1 for char in text if not char.isalnum() and not char.isspace())
    if alnum_count <= 1:
        return True
    return punctuation_count >= max(4, alnum_count * 2)


def _strip_known_unit_filler(text: str) -> str:
    line = text.rstrip()
    lowered = line.lower()
    for known in sorted(KNOWN_UNITS, key=len, reverse=True):
        unit_index = lowered.rfind(known.lower())
        if unit_index == -1:
            continue
        suffix = line[unit_index + len(known) :]
        if not suffix:
            continue
        if _is_filler_suffix(suffix):
            return line[:unit_index] + known
    return line


def _is_filler_suffix(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(char not in {"_", ".", "-", "/", " "} for char in stripped):
        return False
    return stripped.count("_") >= 2 or stripped.count(".") >= 2 or stripped.count("-") >= 2 or "/" in stripped


def _is_embedded_numeric_token(text: str, match: re.Match[str]) -> bool:
    start = match.start()
    end = match.end()
    left_char = text[start - 1] if start > 0 else ""
    right_char = text[end] if end < len(text) else ""
    return bool((left_char and left_char.isalpha()) or (right_char and right_char.isalpha()))


def label_family_key(label: str | None) -> str:
    return normalize_space(label or "").lower()


def line_pattern(text: str) -> str:
    decoded = parse_measurement_line(text)
    parts: list[str] = []
    if decoded.prefix:
        parts.append("<PREFIX>")
    if decoded.label:
        for token in normalize_space(decoded.label).split():
            parts.append(token.lower())
    if decoded.value:
        parts.append("<VALUE>")
    if decoded.unit:
        parts.append(f"<UNIT:{decoded.unit.lower()}>")
    return " ".join(parts) if parts else "<EMPTY>"


def extract_line_from_source(source: str | None) -> str | None:
    if not source:
        return None
    for prefix in ("exact_line:", "ocr_line:", "decoded_line:"):
        if source.startswith(prefix):
            body = source[len(prefix) :].strip()
            if not body:
                return None
            if prefix == "exact_line:":
                parts = body.rsplit(":", maxsplit=1)
                candidate = parts[0] if len(parts) == 2 else body
            else:
                candidate = body
            candidate = candidate.strip()
            return candidate or None
    return None


@dataclass(frozen=True)
class DecodedMeasurementLine:
    raw_text: str
    canonical_text: str
    prefix: str | None
    label: str | None
    value: str | None
    unit: str | None
    syntax_confidence: float
    uncertain_reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_measurement(self) -> bool:
        return self.label is not None and self.value is not None

    @property
    def display_name(self) -> str | None:
        if self.label is None:
            return None
        if self.prefix:
            return f"{self.prefix} {self.label}"
        return self.label

    def to_ai_measurement(self, *, confidence: float, order_hint: int | None = None) -> AiMeasurement | None:
        if not self.is_measurement:
            return None
        assert self.display_name is not None
        return AiMeasurement(
            name=self.display_name,
            value=self.value or "",
            unit=self.unit,
            source=f"exact_line:{self.canonical_text}:{confidence:.3f}",
            order_hint=order_hint,
        )


def parse_measurement_line(text: str) -> DecodedMeasurementLine:
    raw_text = text or ""
    canonical_text = canonicalize_exact_line(raw_text)
    prefix: str | None = None
    body = canonical_text
    reasons: list[str] = []

    prefix_match = _PREFIX_RE.match(canonical_text)
    if prefix_match is not None and re.search(r"[A-Za-z]", prefix_match.group("body")):
        prefix = prefix_match.group("prefix")
        body = prefix_match.group("body").strip()

    label: str | None = None
    value: str | None = None
    unit: str | None = None
    trailing_text = ""
    value_matches = list(_VALUE_RE.finditer(body))

    for match in reversed(value_matches):
        if _is_embedded_numeric_token(body, match):
            continue
        candidate_label = normalize_space(body[: match.start()])
        if not candidate_label or not re.search(r"[A-Za-z%]", candidate_label):
            continue
        candidate_value = normalize_value(match.group(0))
        candidate_trailing = normalize_space(body[match.end() :])
        candidate_unit = normalize_unit(candidate_trailing or None)
        if candidate_trailing and candidate_unit is None:
            trailing_text = candidate_trailing
            continue
        label = candidate_label or None
        value = candidate_value
        unit = candidate_unit
        trailing_text = candidate_trailing
        break

    if label is None:
        value_only_match = _VALUE_ONLY_RE.match(body)
        if value_only_match is not None:
            value = normalize_value(value_only_match.group("value"))
            unit = normalize_unit(value_only_match.group("unit"))
            reasons.append("missing_label")

    if label is None:
        fallback_label = normalize_space(body)
        if fallback_label:
            label = fallback_label if re.search(r"[A-Za-z%]", fallback_label) else None
        reasons.append("missing_value")

    if label is None:
        reasons.append("missing_label")

    if trailing_text and unit is None:
        reasons.append("unknown_unit_suffix")

    syntax_confidence = 1.0
    if "missing_value" in reasons:
        syntax_confidence -= 0.35
    if "missing_label" in reasons:
        syntax_confidence -= 0.35
    if "unknown_unit_suffix" in reasons:
        syntax_confidence -= 0.15
    if prefix and not value:
        syntax_confidence -= 0.05
    syntax_confidence = max(0.0, min(1.0, syntax_confidence))

    return DecodedMeasurementLine(
        raw_text=raw_text,
        canonical_text=canonical_text,
        prefix=prefix,
        label=label,
        value=value,
        unit=unit,
        syntax_confidence=syntax_confidence,
        uncertain_reasons=tuple(dict.fromkeys(reasons)),
    )


def decode_lines_to_measurements(
    lines: list[str],
    *,
    confidence: float,
) -> list[AiMeasurement]:
    measurements: list[AiMeasurement] = []
    for order, line in enumerate(lines):
        decoded = parse_measurement_line(line)
        item = decoded.to_ai_measurement(confidence=confidence, order_hint=order)
        if item is not None:
            measurements.append(item)
    return measurements
