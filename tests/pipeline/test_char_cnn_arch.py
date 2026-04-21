from __future__ import annotations

import torch

from app.pipeline.ocr.char_cnn_arch import CHAR_CNN_VARIANTS, build_char_fallback_cnn


def test_char_cnn_variants_forward() -> None:
    for variant in CHAR_CNN_VARIANTS:
        m = build_char_fallback_cnn(7, variant)
        x = torch.randn(5, 1, 24, 24)
        y = m(x)
        assert y.shape == (5, 7)
