from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.transcription.dead_space_char_splitter import split_dead_space_char_slices


def test_splitter_returns_empty_on_blank_input() -> None:
    img = np.ones((32, 120), dtype=np.uint8) * 255
    result = split_dead_space_char_slices(img)
    assert result.expected_char_count == 0
    assert result.slices == ()
    assert result.confidence == 0.0


def test_splitter_handles_joined_glyphs_without_over_splitting() -> None:
    img = np.ones((36, 180), dtype=np.uint8) * 255
    cv2.putText(img, "111111", (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2, cv2.LINE_AA)
    # bridge neighboring glyphs to stress dead-space assumptions
    cv2.line(img, (18, 20), (150, 20), 0, 1, cv2.LINE_AA)

    result = split_dead_space_char_slices(img, min_column_ratio=0.03)

    # Should not explode into many tiny slices under connected strokes.
    assert result.expected_char_count <= 8
    assert result.expected_char_count >= 1
    for s in result.slices:
        assert s.width >= 2
        assert s.height >= 1


def test_splitter_rejects_low_ink_noise() -> None:
    rng = np.random.default_rng(0)
    img = np.ones((28, 120), dtype=np.uint8) * 255
    noise_mask = rng.random((28, 120)) < 0.015
    img[noise_mask] = 0

    result = split_dead_space_char_slices(img, min_ink_ratio=0.08, min_column_ratio=0.08)
    assert result.expected_char_count == 0
    assert result.confidence == 0.0
