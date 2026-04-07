from __future__ import annotations

import importlib.util

import numpy as np

from app.pipeline.line_segmenter import LineSegmenter
from app.pipeline.ocr_engines import OcrToken


def _make_roi() -> np.ndarray:
    roi = np.zeros((50, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[6:10, 8:44, :] = 255
    roi[18:23, 10:95, :] = 255
    roi[29:34, 12:88, :] = 255
    return roi


def test_line_segmenter_fixed_pitch_line_boxes_without_header_trim() -> None:
    segmenter = LineSegmenter(segmentation_mode="fixed_pitch")

    result = segmenter.segment(_make_roi())

    assert result.header_trim_px == 0
    assert len(result.lines) == 2
    assert result.lines[1].bbox[1] > result.lines[0].bbox[1]
    assert all(line.metadata.get("source") == "fixed_pitch" for line in result.lines)


def test_line_segmenter_recovers_full_content_when_no_text_is_visible() -> None:
    roi = np.zeros((24, 64, 3), dtype=np.uint8)
    segmenter = LineSegmenter()

    result = segmenter.segment(roi)

    assert result.lines
    assert result.lines[0].metadata.get("recovered") is True


def test_line_segmenter_refines_merged_token_row_with_local_projection_split() -> None:
    roi = np.zeros((44, 100, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[4:8, 10:72, :] = 255
    roi[15:19, 12:78, :] = 255
    roi[34:37, 16:60, :] = 255

    tokens = [
        OcrToken(text="merged", confidence=0.9, bbox=(8, 2, 76, 20)),
        OcrToken(text="single", confidence=0.9, bbox=(15, 32, 46, 5)),
    ]
    segmenter = LineSegmenter(
        segmentation_mode="adaptive",
        default_header_trim_px=0,
        min_line_height_px=3,
        line_padding_px=1,
        merge_gap_px=2,
    )
    segmenter.detect_header_trim = lambda _roi: 0  # type: ignore[method-assign]

    result = segmenter.segment(roi, tokens=tokens)

    assert len(result.lines) == 3
    assert result.debug["refined_line_splits"] == 1
    assert [line.metadata.get("refined_split") for line in result.lines] == [True, True, None]
    assert result.lines[0].bbox[1] < result.lines[1].bbox[1]


def test_line_segmenter_normalizes_xyxy_token_boxes_for_dense_panel_rows() -> None:
    roi = np.zeros((64, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[10:14, 8:50, :] = 255
    roi[10:14, 74:112, :] = 255
    roi[21:25, 8:55, :] = 255
    roi[21:25, 73:112, :] = 255
    roi[32:36, 8:58, :] = 255
    roi[32:36, 76:112, :] = 255

    tokens = [
        OcrToken(text="A", confidence=0.9, bbox=(8, 10, 50, 14)),
        OcrToken(text="1", confidence=0.9, bbox=(74, 10, 112, 14)),
        OcrToken(text="B", confidence=0.9, bbox=(8, 21, 55, 25)),
        OcrToken(text="2", confidence=0.9, bbox=(73, 21, 112, 25)),
        OcrToken(text="C", confidence=0.9, bbox=(8, 32, 58, 36)),
        OcrToken(text="3", confidence=0.9, bbox=(76, 32, 112, 36)),
    ]
    segmenter = LineSegmenter(
        segmentation_mode="adaptive",
        default_header_trim_px=0,
        min_line_height_px=3,
        line_padding_px=1,
        merge_gap_px=2,
    )
    segmenter.detect_header_trim = lambda _roi: 0  # type: ignore[method-assign]

    result = segmenter.segment(roi, tokens=tokens)

    assert len(result.lines) == 3
    assert all(line.metadata.get("token_bbox_format") == "xyxy" for line in result.lines)
    assert [line.metadata.get("token_count") for line in result.lines] == [2, 2, 2]


def test_line_segmenter_fixed_pitch_uses_gap_midpoints_for_boundaries() -> None:
    roi = np.zeros((64, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[24:28, 10:100, :] = 255
    roi[44:48, 12:102, :] = 255

    segmenter = LineSegmenter(target_line_height_px=20.0)
    segmenter.detect_header_trim = lambda _roi: 24  # type: ignore[method-assign]

    result = segmenter.segment(roi)

    assert len(result.lines) == 2
    assert result.lines[0].bbox[1] == 24
    assert result.lines[0].bbox[1] + result.lines[0].bbox[3] == result.lines[1].bbox[1]
    assert result.lines[1].bbox[1] == 38
    assert result.lines[0].metadata.get("estimated_line_count") == 2
    assert all(line.metadata.get("placement") == "gap_midpoint" for line in result.lines)


def test_line_segmenter_extra_left_pad_expands_crop_left() -> None:
    roi = np.zeros((64, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[24:28, 10:100, :] = 255
    roi[44:48, 12:102, :] = 255

    tight = LineSegmenter(target_line_height_px=20.0, extra_left_pad_px=0)
    tight.detect_header_trim = lambda _roi: 24  # type: ignore[method-assign]
    loose = LineSegmenter(target_line_height_px=20.0, extra_left_pad_px=16)
    loose.detect_header_trim = lambda _roi: 24  # type: ignore[method-assign]

    r_tight = tight.segment(roi)
    r_loose = loose.segment(roi)
    assert r_loose.lines[0].bbox[0] < r_tight.lines[0].bbox[0]


def test_line_segmenter_fixed_pitch_gap_boundaries_keep_text_covered() -> None:
    roi = np.zeros((64, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[24:28, 10:100, :] = 255
    roi[44:48, 12:102, :] = 255

    segmenter = LineSegmenter(target_line_height_px=20.0, snap_to_valleys=True)
    segmenter.detect_header_trim = lambda _roi: 24  # type: ignore[method-assign]

    result = segmenter.segment(roi)

    assert len(result.lines) == 2
    b0 = result.lines[0].bbox
    b1 = result.lines[1].bbox
    assert b0[1] <= 24 and b0[1] + b0[3] >= 28
    assert b1[1] <= 44 and b1[1] + b1[3] >= 48


def test_line_segmenter_tracks_component_boxes_per_line_when_cv2_is_available() -> None:
    if importlib.util.find_spec("cv2") is None:
        return

    roi = np.zeros((64, 120, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[24:28, 10:32, :] = 255
    roi[24:28, 60:92, :] = 255
    roi[44:48, 12:34, :] = 255
    roi[44:48, 64:96, :] = 255

    segmenter = LineSegmenter(target_line_height_px=20.0, line_padding_px=1)
    segmenter.detect_header_trim = lambda _roi: 24  # type: ignore[method-assign]

    result = segmenter.segment(roi)

    assert len(result.lines) == 2
    assert len(result.lines[0].component_boxes) == 2
    assert len(result.lines[1].component_boxes) == 2
    assert result.lines[0].bbox[0] == 11
    assert result.lines[0].bbox[0] + result.lines[0].bbox[2] == 95


def test_line_segmenter_rescues_weak_short_line_between_stronger_rows() -> None:
    if importlib.util.find_spec("cv2") is None:
        return

    roi = np.zeros((56, 100, 3), dtype=np.uint8)
    roi[:, :, :] = (0x1A, 0x21, 0x29)
    roi[6:10, 10:34, :] = 255
    roi[6:10, 62:88, :] = 255
    roi[20:24, 22:29, :] = 255
    roi[20:24, 34:41, :] = 255
    roi[34:38, 8:42, :] = 255
    roi[34:38, 54:94, :] = 255

    segmenter = LineSegmenter(target_line_height_px=18.0, merge_gap_px=2, min_line_height_px=3)
    segmenter.detect_header_trim = lambda _roi: 0  # type: ignore[method-assign]

    result = segmenter.segment(roi)

    assert len(result.lines) == 3
    assert any(16 <= line.bbox[1] <= 18 for line in result.lines)
