"""
Smoke tests for the GOT-OCR 2.0 abbreviation normalizer.

Run with:
    python -m pytest tests/pipeline/test_gotocr_normalizer.py -v
or:
    python tests/pipeline/test_gotocr_normalizer.py
"""

from __future__ import annotations

import sys
from pathlib import Path
try:
    import pytest
    _PYTEST_AVAILABLE = True
except ImportError:
    _PYTEST_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.ocr.gotocr_normalizer import normalize_gotocr_line, normalize_gotocr_text


# ---------------------------------------------------------------------------
# Parametrized cases: (description, input, expected_output)
# ---------------------------------------------------------------------------

CASES = [
    # --- Suffix fixes (GOT-OCR splits a trailing token) ---
    ("Vmax split",         "AV V max 1.3 m/s",          "AV Vmax 1.3 m/s"),
    ("Vmean split",        "AV V mean 1.0 m/s",          "AV Vmean 1.0 m/s"),
    ("VTI split",          "AV V TI 28 cm",              "AV VTI 28 cm"),
    ("maxPG split",        "AV max PG 6 mmHg",           "AV maxPG 6 mmHg"),
    ("meanPG split",       "AV mean PG 4 mmHg",          "AV meanPG 4 mmHg"),
    ("DecT split",         "MV Dec T 183 ms",            "MV DecT 183 ms"),
    ("Biplane split",      "EF Bi plane 64 %",           "EF Biplane 64 %"),

    # --- Root merges (GOT-OCR splits the abbreviation root itself) ---
    ("LAESV root split",   "LAES V (A-L) 70.05 ml",     "LAESV(A-L) 70.05 ml"),
    ("LAESV inline A-L",   "LAES V A-L A4C 56 ml",      "LAESV A-L A4C 56 ml"),
    ("LVEDV root split",   "LVED V MOD A4C 105.47 ml",  "LVEDV MOD A4C 105.47 ml"),
    ("LVESV root split",   "LVES V MOD A4C 38.32 ml",   "LVESV MOD A4C 38.32 ml"),
    ("LVOT root split",    "LV Ot Vmax 1.1 m/s",        "LVOT Vmax 1.1 m/s"),
    ("LVEF root split",    "LV EF MOD A4C 63.66 %",     "LVEF MOD A4C 63.66 %"),
    ("LVIDd root split",   "LVI Dd 5.4 cm",              "LVIDd 5.4 cm"),
    ("LVPWd root split",   "LVPW d 1.0 cm",              "LVPWd 1.0 cm"),
    ("LVLd root split",    "LV Ld A2C 7.76 cm",          "LVLd A2C 7.76 cm"),
    ("LVLs root split",    "LV Ls A2C 6.07 cm",          "LVLs A2C 6.07 cm"),
    ("LAAs root split",    "LA As A4C 19.5 cm2",         "LAAs A4C 19.5 cm2"),
    ("LALs root split",    "LA Ls A2C 6.0 cm",           "LALs A2C 6.0 cm"),
    ("SV MOD split",       "S V MOD A4C 67.14 ml",       "SV MOD A4C 67.14 ml"),
    ("%FS split",          "% FS 34%",                   "%FS 34%"),
    ("EF(Teich) split",    "E F (Teich) 62%",            "EF(Teich) 62%"),
    ("IVC split (IV C)",   "IV C 2.2 cm",                "IVC 2.2 cm"),
    ("IVC split (I VC)",   "I VC 2.2 cm",                "IVC 2.2 cm"),

    # --- AVA merges (only before Vmax/VTI, not generic "AV A Vel") ---
    ("AVA Vmax split",     "AV A Vmax 2.8 cm2",          "AVA Vmax 2.8 cm2"),
    ("AVA VTI split",      "AV A VTI 19.9 cm",           "AVA VTI 19.9 cm"),
    ("AVA (VTI) split",    "AV A (VTI) 2.3 cm2",         "AVA (VTI) 2.3 cm2"),

    # --- Ratio slash fixes ---
    ("S/D slash space",    "P Vein S / D Ratio 1.2",     "P Vein S/D Ratio 1.2"),

    # --- Unit fixes ---
    ("mmHg space",         "mm Hg",                      "mmHg"),
    ("m/s space",          "m/ s",                       "m/s"),

    # --- Already-correct (must not be mutated) ---
    ("AV Vmax unchanged",  "AV Vmax 1.3 m/s",            "AV Vmax 1.3 m/s"),
    ("TR Vmax unchanged",  "TR Vmax 2.3 m/s",            "TR Vmax 2.3 m/s"),
]


@pytest.mark.parametrize("desc,inp,expected", [(d, i, e) for d, i, e in CASES], ids=[c[0] for c in CASES])
def test_normalize_line(desc: str, inp: str, expected: str) -> None:
    assert normalize_gotocr_line(inp) == expected, f"[{desc}] {inp!r} → {normalize_gotocr_line(inp)!r}, expected {expected!r}"


def test_multiline_text() -> None:
    """Ensure normalize_gotocr_text operates per-line."""
    raw = "AV V max 1.3 m/s\nAV mean PG 4 mmHg\nEF Bi plane 64 %"
    expected = "AV Vmax 1.3 m/s\nAV meanPG 4 mmHg\nEF Biplane 64 %"
    assert normalize_gotocr_text(raw) == expected


if __name__ == "__main__":
    # Quick self-test mode without pytest
    all_pass = True
    for desc, inp, expected in CASES:
        got = normalize_gotocr_line(inp)
        ok = got == expected
        if not ok:
            all_pass = False
        sym = "✓" if ok else "✗"
        print(f"{sym}  [{desc}]")
        if not ok:
            print(f"     IN:  {inp!r}")
            print(f"     EXP: {expected!r}")
            print(f"     GOT: {got!r}")

    print()
    print("ALL PASS" if all_pass else "SOME CASES FAILED")
    sys.exit(0 if all_pass else 1)
