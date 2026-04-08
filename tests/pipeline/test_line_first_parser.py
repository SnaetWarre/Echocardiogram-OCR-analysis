from __future__ import annotations

from app.pipeline.measurements.line_first_parser import LineFirstParser


def test_line_first_parser_decodes_lines_without_regex_tables() -> None:
    parser = LineFirstParser()

    items = parser.parse_lines(["1 IVSd 0.9 cm", "2 LVIDd 5.4 cm"], confidence=0.9)

    assert [item.name for item in items] == ["1 IVSd", "2 LVIDd"]


def test_line_first_parser_returns_empty_when_lines_are_not_decodable() -> None:
    parser = LineFirstParser()

    items = parser.parse_lines(["unclear overlay"], confidence=0.2)

    assert items == []
