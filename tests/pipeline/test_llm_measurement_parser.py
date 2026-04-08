from __future__ import annotations

from app.pipeline.measurements.measurement_parsers import LocalLlmMeasurementParser


def test_restore_leading_index_when_llm_drops_it() -> None:
    indexed_lines = LocalLlmMeasurementParser._extract_indexed_measurement_lines(
        "1 Ao Diam 3.2 cm\n1 LVOT Diam 2.0 cm"
    )

    restored = LocalLlmMeasurementParser._restore_leading_index(
        name="Ao Diam",
        value="3.2",
        unit="cm",
        indexed_lines=indexed_lines,
    )

    assert restored == "1 Ao Diam"


def test_restore_leading_index_when_unit_is_missing_from_llm_output() -> None:
    indexed_lines = LocalLlmMeasurementParser._extract_indexed_measurement_lines(
        "1 LVOT Diam 2.0 cm"
    )

    restored = LocalLlmMeasurementParser._restore_leading_index(
        name="LVOT Diam",
        value="2.0",
        unit=None,
        indexed_lines=indexed_lines,
    )

    assert restored == "1 LVOT Diam"


def test_does_not_restore_leading_index_for_value_mismatch() -> None:
    indexed_lines = LocalLlmMeasurementParser._extract_indexed_measurement_lines(
        "1 Ao Diam 3.2 cm"
    )

    restored = LocalLlmMeasurementParser._restore_leading_index(
        name="Ao Diam",
        value="3.1",
        unit="cm",
        indexed_lines=indexed_lines,
    )

    assert restored is None


def test_does_not_restore_leading_index_when_name_already_has_prefix() -> None:
    indexed_lines = LocalLlmMeasurementParser._extract_indexed_measurement_lines(
        "1 Ao Diam 3.2 cm"
    )

    restored = LocalLlmMeasurementParser._restore_leading_index(
        name="1 Ao Diam",
        value="3.2",
        unit="cm",
        indexed_lines=indexed_lines,
    )

    assert restored is None


def test_extract_indexed_measurement_lines_only_keeps_indexed_measurements() -> None:
    indexed_lines = LocalLlmMeasurementParser._extract_indexed_measurement_lines(
        "1 Ao Diam 3.2 cm\nAo Root 3.0 cm\n2 LVOT Diam 2.0 cm"
    )

    assert indexed_lines == [
        ("1", "Ao Diam", "3.2", "cm"),
        ("2", "LVOT Diam", "2.0", "cm"),
    ]
