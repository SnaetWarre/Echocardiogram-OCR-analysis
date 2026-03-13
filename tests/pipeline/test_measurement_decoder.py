from __future__ import annotations

from app.pipeline.measurement_decoder import (
    canonicalize_exact_line,
    line_pattern,
    parse_measurement_line,
)


def test_canonicalize_exact_line_normalizes_spacing_and_compact_units() -> None:
    assert canonicalize_exact_line(r"1   Ao\,Diam  3.2cm") == "1 Ao Diam 3.2 cm"


def test_parse_measurement_line_extracts_prefix_label_value_unit() -> None:
    decoded = parse_measurement_line("2 LVIDd 5.4 cm")

    assert decoded.prefix == "2"
    assert decoded.label == "LVIDd"
    assert decoded.value == "5.4"
    assert decoded.unit == "cm"
    assert decoded.is_measurement is True


def test_parse_measurement_line_preserves_unknown_label_without_value() -> None:
    decoded = parse_measurement_line("Strange Overlay Label")

    assert decoded.label == "Strange Overlay Label"
    assert decoded.value is None
    assert "missing_value" in decoded.uncertain_reasons
    assert decoded.syntax_confidence < 1.0


def test_line_pattern_converts_numeric_parts_to_generic_tokens() -> None:
    assert line_pattern("3 AV Vmax 1.8 m/s") == "<PREFIX> av vmax <VALUE> <UNIT:m/s>"


def test_canonicalize_exact_line_repairs_common_ocr_label_near_misses() -> None:
    assert canonicalize_exact_line("L¥IDd 5.0 em") == "LVIDd 5.0 cm"
    assert canonicalize_exact_line("1E' Lat 0.09 m/") == "1 E' Lat 0.09 m/s"
    assert canonicalize_exact_line("L¥P¥Wd i1.1em") == "LVPWd i1.1 cm"
    assert canonicalize_exact_line("1LALS AdU 3.6 cM") == "1 LALs A4C 3.6 cm"
    assert canonicalize_exact_line("1 LVYIDS 3.6 cm") == "1 LVIDs 3.6 cm"


def test_canonicalize_exact_line_suppresses_symbol_heavy_junk() -> None:
    assert canonicalize_exact_line("--- - . . _ __ -") == ""


def test_parse_measurement_line_uses_repaired_label_and_unit_aliases() -> None:
    decoded = parse_measurement_line("1E' Lat 0.09 m/")

    assert decoded.prefix == "1"
    assert decoded.label == "E' Lat"
    assert decoded.value == "0.09"
    assert decoded.unit == "m/s"


def test_parse_measurement_line_normalizes_mes_unit_alias() -> None:
    decoded = parse_measurement_line("1 E' Lat 0.09 més")

    assert decoded.label == "E' Lat"
    assert decoded.value == "0.09"
    assert decoded.unit == "m/s"


def test_canonicalize_exact_line_strips_fillers_and_repairs_prefix_noise() -> None:
    assert canonicalize_exact_line("2 LA Diam 5.5 cm ____") == "2 LA Diam 5.5 cm"
    assert canonicalize_exact_line("ı IVSd /1.1 cm/ . . . . .") == "1 IVSd 1.1 cm"
    assert canonicalize_exact_line("LVPVVd 1.1 cm") == "LVPWd 1.1 cm"
