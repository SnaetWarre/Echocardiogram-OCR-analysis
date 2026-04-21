from __future__ import annotations

from pathlib import Path

from app.pipeline.ocr.char_fallback import (
    CharFallbackClassifier,
    TemplateCharFallbackClassifier,
    TorchCharCnnClassifier,
)


def build_char_fallback_classifier(
    artifact_dir: Path,
    *,
    prefer_cnn: bool = True,
    device: str = "cpu",
) -> CharFallbackClassifier | None:
    """Load a char fallback classifier from artifact files.

    Preference order:
    1) Torch CNN artifact (`model.pt` + metadata)
    2) Template artifact (`templates.npz` + charset)
    """
    artifact_dir = artifact_dir.expanduser()
    if prefer_cnn:
        cnn = TorchCharCnnClassifier.from_artifact_dir(artifact_dir, device=device)
        if cnn is not None:
            return cnn

    template = TemplateCharFallbackClassifier.from_artifact_dir(artifact_dir)
    if template is not None and template.is_available:
        return template
    return None
