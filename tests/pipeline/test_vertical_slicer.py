from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.transcription.vertical_slicer import reconstruct_slice_text, slice_line_into_vertical_slices


def test_splitter_returns_empty_on_blank_input() -> None:
    img = np.ones((32, 120), dtype=np.uint8) * 255
    result = slice_line_into_vertical_slices(img)
    assert result.expected_char_count == 0
    assert result.slices == ()
    assert result.confidence == 0.0
    assert result.reliable is False


def test_splitter_handles_joined_glyphs_without_over_splitting() -> None:
    img = np.ones((36, 180), dtype=np.uint8) * 255
    cv2.putText(img, "111111", (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2, cv2.LINE_AA)
    # bridge neighboring glyphs to stress dead-space assumptions
    cv2.line(img, (18, 20), (150, 20), 0, 1, cv2.LINE_AA)

    result = slice_line_into_vertical_slices(img)

    assert result.expected_char_count == 0
    assert result.reliable is False
    for s in result.slices:
        assert s.width >= 2
        assert s.height == result.preprocessed_line.shape[0]


def test_splitter_rejects_low_ink_noise() -> None:
    rng = np.random.default_rng(0)
    img = np.ones((28, 120), dtype=np.uint8) * 255
    noise_mask = rng.random((28, 120)) < 0.015
    img[noise_mask] = 0

    result = slice_line_into_vertical_slices(img, min_ink_ratio=0.08)
    assert result.expected_char_count == 0
    assert result.confidence == 0.0


def test_splitter_keeps_count_for_separated_narrow_runs() -> None:
    img = np.ones((24, 80), dtype=np.uint8) * 255
    for x in (6, 22, 38, 54):
        cv2.rectangle(img, (x, 4), (x + 5, 20), 0, -1)

    result = slice_line_into_vertical_slices(img)

    assert result.expected_char_count == 4
    assert len(result.slices) == 4
    assert result.confidence > 0.0
    assert result.reliable is True


def test_splitter_reconstructs_single_spaces_from_large_gaps() -> None:
    img = np.ones((28, 120), dtype=np.uint8) * 255
    for x in (4, 14, 24, 46, 56, 78):
        cv2.rectangle(img, (x, 5), (x + 5, 22), 0, -1)

    result = slice_line_into_vertical_slices(img)

    assert result.expected_char_count == 6
    assert list(result.space_after) == [False, False, True, False, True]
    assert reconstruct_slice_text(result, ("%", "F", "S", "1", "6", "%")) == "%FS 16 %"
