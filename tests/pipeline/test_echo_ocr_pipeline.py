from __future__ import annotations

import numpy as np

from app.pipeline.echo_ocr_pipeline import RegexMeasurementParser, TopLeftBlueGrayBoxDetector
from app.pipeline.measurement_parsers import LocalLlmMeasurementParser, LocalLlmParserConfig


def test_detector_finds_top_left_box() -> None:
    frame = np.zeros((120, 200, 3), dtype=np.uint8)
    frame[8:30, 10:90, 0] = 95
    frame[8:30, 10:90, 1] = 115
    frame[8:30, 10:90, 2] = 135

    detector = TopLeftBlueGrayBoxDetector(min_pixels=100)
    detection = detector.detect(frame)

    assert detection.present is True
    assert detection.bbox is not None
    x, y, width, height = detection.bbox
    assert x <= 12
    assert y <= 10
    assert width >= 70
    assert height >= 18


def test_parser_extracts_value_and_unit() -> None:
    parser = RegexMeasurementParser()
    text = "PV Vmax 0.87 m/s\nPV maxPG 3 mmHg"
    items = parser.parse(text, confidence=0.9)

    assert len(items) == 2
    assert items[0].name == "PV Vmax"
    assert items[0].value == "0.87"
    assert items[0].unit == "m/s"
    assert items[1].name == "PV maxPG"
    assert items[1].value == "3"
    assert items[1].unit == "mmHg"


def test_parser_canonicalizes_compact_labels() -> None:
    parser = RegexMeasurementParser()
    text = "TRmaxPG 14 mmHg\nAVVmax 1.3 m/s\nLAESV index(a-l) 31.99 ml/m2"
    items = parser.parse(text, confidence=0.9)
    by_name = {item.name: item for item in items}

    assert "TR maxPG" in by_name
    assert by_name["TR maxPG"].value == "14"
    assert by_name["TR maxPG"].unit == "mmHg"

    assert "AV Vmax" in by_name
    assert by_name["AV Vmax"].value == "1.3"
    assert by_name["AV Vmax"].unit == "m/s"

    assert "LAESV index (A-L)" in by_name
    assert by_name["LAESV index (A-L)"].value == "31.99"
    assert by_name["LAESV index (A-L)"].unit == "ml/m2"


def test_parser_multiline_join_and_unit_completion() -> None:
    parser = RegexMeasurementParser()
    text = "\n".join(
        [
            "TR",
            "Vmax",
            "1.9",
            "AVPG",
            "(mean)",
            "4",
            "e'",
            "sept",
            "0.08",
            "ms",
        ]
    )
    items = parser.parse(text, confidence=0.9)
    by_name = {item.name: item for item in items}

    assert "TR Vmax" in by_name
    assert by_name["TR Vmax"].value == "1.9"
    assert by_name["TR Vmax"].unit == "m/s"

    assert "AV meanPG" in by_name
    assert by_name["AV meanPG"].value == "4"
    assert by_name["AV meanPG"].unit == "mmHg"

    assert "e' sept" in by_name
    assert by_name["e' sept"].value == "0.08"
    assert by_name["e' sept"].unit == "m/s"


def test_local_llm_parser_uses_nuextract_prompt_shape() -> None:
    parser = LocalLlmMeasurementParser(
        config=LocalLlmParserConfig(model="nuextract:latest", command="ollama", timeout_s=5.0)
    )
    prompt = parser._build_prompt("PV Vmax 0.87 m/s")

    assert "### Template:" in prompt
    assert '"measurements"' in prompt
    assert "### Text:" in prompt
