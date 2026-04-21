"""Char-fallback CNN backbones (training + inference must use the same variant)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import torch.nn as nn

if TYPE_CHECKING:
    import torch

CHAR_CNN_VARIANTS: Final[tuple[str, ...]] = ("tiny", "medium", "large")


class _TinyCharCnn(nn.Module):
    """Original compact head (~48-dim embedding)."""

    def __init__(self, class_count: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 48, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Linear(48, class_count)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        feats = self.features(x)
        return self.classifier(feats.flatten(1))


class _MediumCharCnn(nn.Module):
    """Deeper / wider; still cheap at 24×24 input."""

    def __init__(self, class_count: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 48, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(48),
            nn.MaxPool2d(2),
            nn.Conv2d(48, 96, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(96),
            nn.MaxPool2d(2),
            nn.Conv2d(96, 160, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(160),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Linear(160, class_count)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        feats = self.features(x)
        return self.classifier(feats.flatten(1))


class _LargeCharCnn(nn.Module):
    """Heavier backbone for harder glyphs; inference stays one batched forward per line."""

    def __init__(self, class_count: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(64),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(128),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(256),
            nn.MaxPool2d(2),
            nn.Conv2d(256, 384, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.BatchNorm2d(384),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Linear(384, class_count)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        feats = self.features(x)
        return self.classifier(feats.flatten(1))


def build_char_fallback_cnn(class_count: int, variant: str) -> nn.Module:
    key = (variant or "medium").strip().lower()
    if key == "tiny":
        return _TinyCharCnn(class_count)
    if key == "medium":
        return _MediumCharCnn(class_count)
    if key == "large":
        return _LargeCharCnn(class_count)
    raise ValueError(f"Unknown cnn_variant {variant!r}; expected one of {CHAR_CNN_VARIANTS}")


def default_cnn_variant() -> str:
    return "medium"
