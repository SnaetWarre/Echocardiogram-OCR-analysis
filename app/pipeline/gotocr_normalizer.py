"""
GOT-OCR 2.0 output normalizer.

GOT-OCR 2.0 can both *split* tokens (inserting spurious spaces inside
abbreviations) and *fuse* tokens (running separate abbreviations together
without spaces).  This module corrects both problems before the text is
handed to the measurement parser.

Observed patterns from the benchmark dataset
--------------------------------------------
Split problems (space inserted inside an abbreviation):
  - "AV V max"    → "AV Vmax"
  - "AV max PG"   → "AV maxPG"
  - "MV Dec T"    → "MV DecT"
  - "EF Bi plane" → "EF Biplane"
  - "LAES V"      → "LAESV"
  - "L VI Dd"     → "LVIDd"
  - "L VP Wd"     → "LVPWd"
  - "L VED V"     → "LVEDV"
  - "L VES V"     → "LVESV"
  - "LA E SV"     → "LAESV"
  - "1 LAL s"     → "LALs"   (frame-number prefix stripped first)

Fuse problems (space missing between separate tokens):
  - "PVVmax"      → "PV Vmax"
  - "PVmaxPG"     → "PV maxPG"
  - "LVOTVmax"    → "LVOT Vmax"
  - "LVOTmaxPG"   → "LVOT maxPG"
  - "LVOTVTI"     → "LVOT VTI"
  - "AVVmax"      → "AV Vmax"
  - "AVmaxPG"     → "AV maxPG"
  - "AVmeanPG"    → "AV meanPG"
  - "AVVTI"       → "AV VTI"
  - "LVOTDiam"    → "LVOT Diam"
  - "2RALENGTH"   → "RA LENGTH"  (also strips leading digit prefix)
  - "MODA4C"      → "MOD A4C"   (view suffix attached to MOD)
  - "LVLdA4C"     → "LVLd A4C"

Other:
  - "E'Lat"       → "E' Lat"    (missing space after apostrophe)
  - "E Sept"      → "E' Sept"   (missing apostrophe)
  - "AVA(VT I)"   → "AVA (VTI)"  (space mis-placed inside VTI)
  - "0:03"        → "0.03"       (colon used as decimal separator)
  - Leading frame-number noise: "1 IVSd" → "IVSd"
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Phase 0: Strip leading noise (frame number prefixes like "1 ", "15 ", etc.)
# We only strip a leading digit(s) if it's followed by a space and then a
# known label prefix — to avoid nuking genuine standalone measurements.
# ---------------------------------------------------------------------------

# Known first-word prefixes that should never start with a bare digit.
_KNOWN_LABEL_PREFIXES = (
    "IVSd", "LVI", "LVP", "LVE", "LVL", "LVOT", "LVEF", "LVESV", "LVEDV",
    "LAL", "LAA", "LAESV", "LAES", "LA", "RA",
    "AV", "AVA", "TR", "PV", "MV", "SV", "EF", "Ao", "RVI", "IVC",
    "E'", "E ", "P Vein",
)

_LEADING_DIGIT_RE = re.compile(r"^\d+\s+")


def _strip_leading_frame_number(line: str) -> str:
    """Remove a leading frame-number token (e.g. '1 ', '15 ') if the rest
    of the line starts with a known echocardiography abbreviation."""
    m = _LEADING_DIGIT_RE.match(line)
    if m:
        rest = line[m.end():]
        if any(rest.startswith(p) for p in _KNOWN_LABEL_PREFIXES):
            return rest
    return line


# ---------------------------------------------------------------------------
# Phase 1: Fix fused tokens (GOT-OCR omits space between adjacent tokens).
# Order matters: longest / most specific patterns first.
# ---------------------------------------------------------------------------

_FUSE_FIXES: list[tuple[re.Pattern[str], str]] = [
    # Compound view suffixes glued onto preceding tokens: "MODA4C" → "MOD A4C"
    # Also handles "MOD A 4 C" (space between 4 and C) → "MOD A4C"
    # Must come before any root merges that reference MOD.
    (re.compile(r"\bMOD\s*A\s*([24])\s*C\b"), r"MOD A\g<1>C"),

    # LVOT + suffix
    (re.compile(r"\bLVOTVmax\b",   re.IGNORECASE), "LVOT Vmax"),
    (re.compile(r"\bLVOTVmean\b",  re.IGNORECASE), "LVOT Vmean"),
    (re.compile(r"\bLVOTmaxPG\b",  re.IGNORECASE), "LVOT maxPG"),
    (re.compile(r"\bLVOTmeanPG\b", re.IGNORECASE), "LVOT meanPG"),
    (re.compile(r"\bLVOTVTI\b",    re.IGNORECASE), "LVOT VTI"),
    (re.compile(r"\bLVOTDiam\b",   re.IGNORECASE), "LVOT Diam"),

    # AV + suffix (but NOT AVA)
    (re.compile(r"\bAVVmax\b",    re.IGNORECASE), "AV Vmax"),
    (re.compile(r"\bAVVmean\b",   re.IGNORECASE), "AV Vmean"),
    (re.compile(r"\bAVmaxPG\b",   re.IGNORECASE), "AV maxPG"),
    (re.compile(r"\bAVmeanPG\b",  re.IGNORECASE), "AV meanPG"),
    (re.compile(r"\bAVVTI\b",     re.IGNORECASE), "AV VTI"),

    # PV + suffix
    (re.compile(r"\bPVVmax\b",    re.IGNORECASE), "PV Vmax"),
    (re.compile(r"\bPVmaxPG\b",   re.IGNORECASE), "PV maxPG"),
    (re.compile(r"\bPVmeanPG\b",  re.IGNORECASE), "PV meanPG"),
    (re.compile(r"\bPVVTI\b",     re.IGNORECASE), "PV VTI"),

    # TR + suffix
    (re.compile(r"\bTRVmax\b",    re.IGNORECASE), "TR Vmax"),
    (re.compile(r"\bTRmaxPG\b",   re.IGNORECASE), "TR maxPG"),

    # MV + suffix
    (re.compile(r"\bMVDecT\b",    re.IGNORECASE), "MV DecT"),

    # LVLd/LVLs glued to view suffix: "LVLdA4C" → "LVLd A4C"
    # Also handles "LV LdA4C" (split root + fused suffix)
    (re.compile(r"\bLVLd\s*A\s*([24])\s*C\b"), r"LVLd A\g<1>C"),
    (re.compile(r"\bLVLs\s*A\s*([24])\s*C\b"), r"LVLs A\g<1>C"),
    (re.compile(r"\bLV\s+Ld\s*A\s*([24])\s*C\b"), r"LVLd A\g<1>C"),
    (re.compile(r"\bLV\s+Ls\s*A\s*([24])\s*C\b"), r"LVLs A\g<1>C"),

    # LALs / LAAs glued to view suffix: "LALsA4C" → "LALs A4C"
    (re.compile(r"\bLALs\s*A\s*([24])\s*C\b"), r"LALs A\g<1>C"),
    (re.compile(r"\bLAAs\s*A\s*([24])\s*C\b"), r"LAAs A\g<1>C"),
    # "LAL s A 4 C" → "LALs A4C"
    (re.compile(r"\bLAL\s+s\s*A\s*([24])\s*C\b", re.IGNORECASE), r"LALs A\g<1>C"),

    # "LAESVA-LA4C" / "LAESVA-LA2C" → "LAESV A-L A4C"
    (re.compile(r"\bLAESV\s*A-L\s*A\s*([24])\s*C\b"), r"LAESV A-L A\g<1>C"),
    # "LA E SVA-LA4C" → "LAESV A-L A4C"
    (re.compile(r"\bLA\s*E\s*SV\s*A-L\s*A\s*([24])\s*C\b"), r"LAESV A-L A\g<1>C"),

    # No-space compound labels like "2RALENGTH5.9cm" → "RA LENGTH 5.9 cm"
    (re.compile(r"\d+\s*RALENGTH\s*([\d.]+)\s*cm\b", re.IGNORECASE), r"RA LENGTH \1 cm"),
    (re.compile(r"\d+\s*LALENGTH\s*([\d.]+)\s*cm\b", re.IGNORECASE), r"LA LENGTH \1 cm"),
    (re.compile(r"\bRALENGTH\s*([\d.]+)\s*cm\b",     re.IGNORECASE), r"RA LENGTH \1 cm"),
    (re.compile(r"\bLALENGTH\s*([\d.]+)\s*cm\b",     re.IGNORECASE), r"LA LENGTH \1 cm"),

    # "E'Lat" → "E' Lat"   (space missing after apostrophe)
    (re.compile(r"\bE'Lat\b",  re.IGNORECASE), "E' Lat"),
    (re.compile(r"\bE'Sept\b", re.IGNORECASE), "E' Sept"),

    # "AVA(VT I)" / "AVA(VT\s*I)" → "AVA (VTI)"
    (re.compile(r"\bAVA\s*\(\s*VT\s+I\s*\)", re.IGNORECASE), "AVA (VTI)"),

    # "(VT I)" inside AV VTI context
    (re.compile(r"\bVT\s+I\b"), "VTI"),
]


# ---------------------------------------------------------------------------
# Phase 2: Fix split tokens (GOT-OCR inserts space inside abbreviation).
# Applied AFTER fuse fixes so the tokens are already stable.
# ---------------------------------------------------------------------------

_SPLIT_FIXES: list[tuple[re.Pattern[str], str]] = [
    # --- Volume/function root splits ---
    # "L VED V" → "LVEDV"
    (re.compile(r"\bL\s+VED\s+V\b"), "LVEDV"),
    # "LVED V" → "LVEDV"
    (re.compile(r"\bLVED\s+V\b"), "LVEDV"),
    # "L VES V" → "LVESV"
    (re.compile(r"\bL\s+VES\s+V\b"), "LVESV"),
    # "LVES V" → "LVESV"
    (re.compile(r"\bLVES\s+V\b"), "LVESV"),
    # "LA E SV" → "LAESV"
    (re.compile(r"\bLA\s+E\s+SV\b"), "LAESV"),
    # "LAES V" → "LAESV"
    (re.compile(r"\bLAES\s+V\b"), "LAESV"),
    # After merging LAESV, collapse space before "(A-L)"
    (re.compile(r"\bLAESV\s+\("), "LAESV("),

    # "L VI Dd" → "LVIDd"
    (re.compile(r"\bL\s+VI\s+Dd\b", re.IGNORECASE), "LVIDd"),
    # "LVI Dd" → "LVIDd"
    (re.compile(r"\bLVI\s+Dd\b",    re.IGNORECASE), "LVIDd"),
    # "L VI Ds" / "LVI Ds" → "LVIDs"
    (re.compile(r"\bL\s+VI\s+Ds\b", re.IGNORECASE), "LVIDs"),
    (re.compile(r"\bLVI\s+Ds\b",    re.IGNORECASE), "LVIDs"),

    # "L VP Wd" → "LVPWd"
    (re.compile(r"\bL\s+VP\s+Wd\b", re.IGNORECASE), "LVPWd"),
    # "LVPW d" → "LVPWd"
    (re.compile(r"\bLVPW\s+d\b",    re.IGNORECASE), "LVPWd"),

    # "1 VSd" / "IV Sd" → "IVSd"
    (re.compile(r"\b1\s+VSd\b",  re.IGNORECASE), "IVSd"),
    (re.compile(r"\bIV\s+Sd\b",  re.IGNORECASE), "IVSd"),

    # "LV Ld" → "LVLd",  "LV Ls" → "LVLs"
    (re.compile(r"\bLV\s+Ld\b"), "LVLd"),
    (re.compile(r"\bLV\s+Ls\b"), "LVLs"),
    # "1 LV LdA4C" → already handled if fuse ran first; but guard the plain split
    (re.compile(r"\b1\s+LV\s+Ld\b"), "LVLd"),
    (re.compile(r"\b1\s+LV\s+Ls\b"), "LVLs"),

    # "LA As" → "LAAs",  "LA Ls" → "LALs"
    (re.compile(r"\bLA\s+As\b"), "LAAs"),
    (re.compile(r"\bLA\s+Ls\b"), "LALs"),
    # "1 LAL s" → "LALs"
    (re.compile(r"\b1\s+LAL\s+s\b", re.IGNORECASE), "LALs"),
    # "LAL s" → "LALs"
    (re.compile(r"\bLAL\s+s\b",     re.IGNORECASE), "LALs"),

    # "Ao As c" → "Ao asc"
    (re.compile(r"\bAo\s+As\s+c\b"), "Ao asc"),
    # "Ao as c" → "Ao asc"
    (re.compile(r"\bAo\s+as\s+c\b"), "Ao asc"),

    # --- E-prime splits ---
    # "E' Lat" / "E' Sept"  — space after apostrophe already correct; guard fused variants
    (re.compile(r"\bE'\s+Lat\b",  re.IGNORECASE), "E' Lat"),
    (re.compile(r"\bE'\s+Sept\b", re.IGNORECASE), "E' Sept"),
    # "E Sept" with missing apostrophe
    (re.compile(r"\bE\s+Sept\b",  re.IGNORECASE), "E' Sept"),

    # --- Suffix splits (space inserted inside compound suffix) ---
    # "V max" → "Vmax",  "V mean" → "Vmean",  "V TI" → "VTI"
    (re.compile(r"\bV\s+max\b",  re.IGNORECASE), "Vmax"),
    (re.compile(r"\bV\s+mean\b", re.IGNORECASE), "Vmean"),
    (re.compile(r"\bV\s+TI\b",   re.IGNORECASE), "VTI"),
    # "max PG" → "maxPG",  "mean PG" → "meanPG"
    (re.compile(r"\bmax\s+PG\b",  re.IGNORECASE), "maxPG"),
    (re.compile(r"\bmean\s+PG\b", re.IGNORECASE), "meanPG"),
    # "Dec T" → "DecT",  "Dec Slope" passes through (keep as-is)
    (re.compile(r"\bDec\s+T\b",     re.IGNORECASE), "DecT"),
    # "Bi plane" → "Biplane"
    (re.compile(r"\bBi\s+plane\b",  re.IGNORECASE), "Biplane"),
    # "% FS" → "%FS"
    (re.compile(r"%\s+FS\b"), "%FS"),

    # --- EF compound splits ---
    (re.compile(r"\bE\s+F\s+\(Teich\)", re.IGNORECASE), "EF(Teich)"),
    (re.compile(r"\bE\s+F\s+Biplane\b", re.IGNORECASE), "EF Biplane"),
    (re.compile(r"\bE\s+F\s+MOD\b",     re.IGNORECASE), "EF MOD"),

    # --- LVOT/LVEF root splits ---
    (re.compile(r"\bLV\s+Ot\b",  re.IGNORECASE), "LVOT"),
    (re.compile(r"\bLV\s+Ef\b",  re.IGNORECASE), "LVEF"),
    (re.compile(r"\bLV\s+EF\b"),                  "LVEF"),

    # --- IVC splits ---
    (re.compile(r"\bI\s+VC\b"), "IVC"),
    (re.compile(r"\bIV\s+C\b"), "IVC"),

    # --- RVIDd splits ---
    (re.compile(r"\bRVI\s+Dd\b",  re.IGNORECASE), "RVIDd"),
    (re.compile(r"\bi\s+Rvid\b",  re.IGNORECASE), "RVIDd"),  # "i RviDd" → noise prefix

    # --- SV MOD ---
    (re.compile(r"\bS\s+V\s+MOD\b", re.IGNORECASE), "SV MOD"),

    # --- Ratio slashes ---
    (re.compile(r"\bS\s*/\s*D\b"), "S/D"),
    (re.compile(r"\bE\s*/\s*A\b"), "E/A"),

    # --- AVA (only before Vmax/VTI) ---
    (re.compile(r"\bAV\s+A\s+(?=Vmax\b)",  re.IGNORECASE), "AVA "),
    (re.compile(r"\bAV\s+A\s+(?=VTI\b)",   re.IGNORECASE), "AVA "),
    (re.compile(r"\bAV\s+A\s+(?=\(VTI\))"),               "AVA "),
]


# ---------------------------------------------------------------------------
# Phase 3: Unit normalisations.
# ---------------------------------------------------------------------------

_UNIT_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bm\s*/\s*s\b"),            "m/s"),
    (re.compile(r"\bmm\s+Hg\b", re.IGNORECASE), "mmHg"),
    (re.compile(r"\bcm\s*2\b"),               "cm2"),
    (re.compile(r"\bml\s*/\s*m\s*2\b", re.IGNORECASE), "ml/m2"),
    (re.compile(r"\bcm\s*/\s*s\b"),           "cm/s"),
    # "m/s 2" / "m/s2" → "m/s2"  (acceleration unit)
    (re.compile(r"\bm/s\s+2\b"),              "m/s2"),
]


# ---------------------------------------------------------------------------
# Phase 4: Value decimal separator fix ("0:03" → "0.03")
# ---------------------------------------------------------------------------

_COLON_DECIMAL_RE = re.compile(r"\b(\d+):(\d{2})\b")


def _fix_colon_decimal(line: str) -> str:
    """Replace colon used as decimal separator in numeric values."""
    return _COLON_DECIMAL_RE.sub(r"\1.\2", line)


# ---------------------------------------------------------------------------
# Phase 5: Line-splitting.
# GOT-OCR often returns all measurements on a single long line.
# We insert newlines before each known label prefix so the regex parser
# sees one measurement per line.
# ---------------------------------------------------------------------------

# Ordered from longest to shortest to avoid partial matches.
_LABEL_SPLIT_RE = re.compile(
    r"(?<=[\d\w])\s+"  # must be preceded by a word/digit char
    r"(?="  # lookahead for known label prefix
    r"(?:"
    # Multi-char prefixes (longest first)
    r"LAESV(?:\s*\(|\s+(?:Index|A-L))"
    r"|LVEDV|LVESV|LVEF|LVOT|LVIDd|LVIDs|LVPWd|LVLd|LVLs|LALs|LAAs"
    r"|MV\s+(?:E\s+VEL|A\s+Vel|Dec|E/A)"
    r"|P\s+Vein\s+(?:A|D|S)"
    r"|EF\s*(?:Biplane|\(Teich\)|MOD)"
    r"|SV\s+MOD"
    r"|TR\s+(?:Vmax|maxPG)"
    r"|PV\s+(?:Vmax|maxPG)"
    r"|AV\s+(?:Vmax|Vmean|maxPG|meanPG|VTI)"
    r"|AVA\s+(?:Vmax|VTI|\(VTI\))"
    r"|LVOT\s+(?:Vmax|maxPG|VTI|Diam)"
    r"|RA\s+LENGTH|LA\s+LENGTH"
    r"|IVSd|IVSDd|LVIDd|LVIDs|LVPWd"
    r"|E'\s+(?:Lat|Sept)"
    r"|%FS"
    r")"
    r")",
    re.IGNORECASE,
)


def _split_into_measurement_lines(text: str) -> str:
    """Insert newlines before each measurement label on a single long line."""
    return _LABEL_SPLIT_RE.sub("\n", text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_gotocr_line(line: str) -> str:
    """Apply all GOT-OCR normalisations to a single line of OCR output."""
    line = _strip_leading_frame_number(line)
    line = _fix_colon_decimal(line)

    # Phase 1: fuse fixes (merge tokens that are glued together)
    for pattern, replacement in _FUSE_FIXES:
        line = pattern.sub(replacement, line)

    # Phase 2: split fixes (re-join tokens that were split apart)
    for pattern, replacement in _SPLIT_FIXES:
        line = pattern.sub(replacement, line)

    # Phase 3: unit dressing
    for pattern, replacement in _UNIT_FIXES:
        line = pattern.sub(replacement, line)

    return line


def normalize_gotocr_text(text: str) -> str:
    """Normalise a full (possibly multi-line) GOT-OCR transcript.

    GOT-OCR often returns its output as a single long space-separated line.
    We:
      1. Apply per-line token normalizations.
      2. Split each line into one-measurement-per-line so the regex parser
         can find all measurements (it processes lines individually).
    """
    lines = text.splitlines()
    normalised_lines: list[str] = []
    for line in lines:
        line = normalize_gotocr_line(line)
        # After token fixes, try to split a long line into measurement lines
        line = _split_into_measurement_lines(line)
        normalised_lines.append(line)
    return "\n".join(normalised_lines)
