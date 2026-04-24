from __future__ import annotations

from app.pipeline.measurements.whole_blob_line_recovery import recover_lines_from_blob_text


def test_recover_lines_from_blob_text_preserves_explicit_newlines_when_count_matches() -> None:
    recovered, debug = recover_lines_from_blob_text(
        "1 LVOT Diam 2.1 cm\n2 AV Vmax 2.5 m/s",
        target_line_count=2,
    )

    assert recovered == [
        "1 LVOT Diam 2.1 cm",
        "2 AV Vmax 2.5 m/s",
    ]
    assert debug["source"] == "raw_newlines"


def test_recover_lines_from_blob_text_splits_single_blob_into_target_line_count() -> None:
    recovered, debug = recover_lines_from_blob_text(
        "1 LVOT Diam 2.1 cm 2 AV Vmax 2.5 m/s",
        target_line_count=2,
    )

    assert recovered == [
        "1 LVOT Diam 2.1 cm",
        "2 AV Vmax 2.5 m/s",
    ]
    assert debug["source"] in {"dp_token_segmentation", "unit_boundary_split"}


def test_recover_lines_from_blob_text_does_not_force_extra_lines_for_clean_single_measurement() -> None:
    recovered, debug = recover_lines_from_blob_text(
        "1 LVOT Diam 2.1 cm",
        target_line_count=3,
    )

    assert recovered == ["1 LVOT Diam 2.1 cm"]
    assert debug["selected_line_count"] == 1


def test_recover_lines_from_blob_text_keeps_existing_multiline_ocr_even_if_target_count_is_higher() -> None:
    recovered, debug = recover_lines_from_blob_text(
        "1 IVSd 1.2 cm\nLVIDd 4.7 cm\nLVPWd 1.1 cm",
        target_line_count=4,
    )

    assert recovered == [
        "1 IVSd 1.2 cm",
        "LVIDd 4.7 cm",
        "LVPWd 1.1 cm",
    ]
    assert debug["source"] == "raw_newlines_relaxed"


def test_recover_lines_from_blob_text_splits_measurements_on_unit_boundaries() -> None:
    recovered, debug = recover_lines_from_blob_text(
        "1 LALs A4C 6.1 cm LAAs A4C 23.4 cm2 LAESV A-L A4C 77 ml",
        target_line_count=4,
    )

    assert recovered == [
        "1 LALs A4C 6.1 cm",
        "LAAs A4C 23.4 cm2",
        "LAESV A-L A4C 77 ml",
    ]
    assert debug["source"] == "unit_boundary_split"
