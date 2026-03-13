from __future__ import annotations

import numpy as np

from app.pipeline.line_segmenter import LineSegmenter


def _make_roi() -> np.ndarray:
    roi = np.zeros((50, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[6:10, 8:44, :] = 255
    roi[18:23, 10:95, :] = 255
    roi[29:34, 12:88, :] = 255
    return roi


def test_line_segmenter_detects_header_trim_and_line_boxes() -> None:
    segmenter = LineSegmenter()

    result = segmenter.segment(_make_roi())

    assert result.header_trim_px >= 10
    assert len(result.lines) == 2
    assert result.lines[0].bbox[1] >= result.header_trim_px
    assert result.lines[1].bbox[1] > result.lines[0].bbox[1]


def test_line_segmenter_recovers_full_content_when_no_text_is_visible() -> None:
    roi = np.zeros((24, 64, 3), dtype=np.uint8)
    segmenter = LineSegmenter()

    result = segmenter.segment(roi)

    assert result.lines
    assert result.lines[0].metadata.get("recovered") is True
