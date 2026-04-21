from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from app.pipeline.ocr.char_cnn_arch import build_char_fallback_cnn
from app.pipeline.transcription.dead_space_char_splitter import CharSlice

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - optional dependency
    torch = None
    nn = None


class CharFallbackClassifier(Protocol):
    def predict(self, line_image: np.ndarray, slices: tuple[CharSlice, ...]) -> "CharFallbackPrediction": ...


@dataclass(frozen=True)
class CharFallbackPrediction:
    text: str
    confidence: float
    per_char_confidence: tuple[float, ...]
    predicted_count: int
    per_char_prediction: tuple[str, ...] = ()

    @property
    def min_char_confidence(self) -> float:
        if not self.per_char_confidence:
            return 0.0
        return float(min(self.per_char_confidence))


class TorchCharCnnClassifier:
    def __init__(
        self,
        *,
        charset: str,
        input_size: int,
        mean: float,
        std: float,
        model_state: dict[str, object],
        device: str = "cpu",
        cnn_variant: str = "tiny",
    ) -> None:
        if torch is None or nn is None:
            raise RuntimeError("TorchCharCnnClassifier requires torch to be installed.")
        self.charset = charset
        self.input_size = int(input_size)
        self.mean = float(mean)
        self.std = float(std) if abs(float(std)) > 1e-8 else 1.0
        self.device = str(device)
        self._cnn_variant = str(cnn_variant or "tiny").strip().lower()

        model = build_char_fallback_cnn(len(charset), self._cnn_variant)
        model.load_state_dict(model_state)
        model.to(self.device)
        model.eval()
        self.model = model

    @classmethod
    def from_artifact_dir(cls, artifact_dir: Path, *, device: str = "cpu") -> "TorchCharCnnClassifier | None":
        if torch is None:
            return None
        model_path = artifact_dir / "model.pt"
        meta_path = artifact_dir / "charset.json"
        norm_path = artifact_dir / "normalization.json"
        if not model_path.exists() or not meta_path.exists():
            return None

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        charset = str(meta.get("charset") or "")
        input_size = int(meta.get("input_size") or 24)
        cnn_variant = str(meta.get("cnn_variant") or "tiny").strip().lower()
        if not charset:
            return None

        mean = 0.5
        std = 0.25
        if norm_path.exists():
            norm = json.loads(norm_path.read_text(encoding="utf-8"))
            mean = float(norm.get("mean", mean))
            std = float(norm.get("std", std))

        state = torch.load(model_path, map_location=device)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        if not isinstance(state, dict):
            return None

        return cls(
            charset=charset,
            input_size=input_size,
            mean=mean,
            std=std,
            model_state=state,
            device=device,
            cnn_variant=cnn_variant,
        )

    def predict(self, line_image: np.ndarray, slices: tuple[CharSlice, ...]) -> CharFallbackPrediction:
        if not slices:
            return CharFallbackPrediction(text="", confidence=0.0, per_char_confidence=(), predicted_count=0)

        gray = _to_gray(line_image)
        batch: list[np.ndarray] = []
        valid: list[bool] = []
        for s in slices:
            x1 = max(0, int(s.x))
            y1 = max(0, int(s.y))
            x2 = min(gray.shape[1], x1 + int(s.width))
            y2 = min(gray.shape[0], y1 + int(s.height))
            if x2 <= x1 or y2 <= y1:
                valid.append(False)
                batch.append(
                    np.zeros((1, self.input_size, self.input_size), dtype=np.float32),
                )
                continue
            crop = gray[y1:y2, x1:x2]
            arr = _normalize_crop_for_cnn(crop, self.input_size, self.mean, self.std)
            valid.append(True)
            batch.append(arr)

        if torch is None or not any(valid):
            return CharFallbackPrediction(text="", confidence=0.0, per_char_confidence=(), predicted_count=0)

        stacked = np.stack(batch, axis=0)
        tensor = torch.from_numpy(stacked).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).detach().cpu().numpy()

        predicted: list[str] = []
        confs: list[float] = []
        for i, s in enumerate(slices):
            if not valid[i]:
                continue
            row = probs[i]
            idx = int(np.argmax(row))
            conf = float(row[idx])
            predicted.append(self.charset[idx])
            confs.append(conf)

        if not predicted:
            return CharFallbackPrediction(text="", confidence=0.0, per_char_confidence=(), predicted_count=0)
        return CharFallbackPrediction(
            text="".join(predicted),
            confidence=float(np.mean(confs)),
            per_char_confidence=tuple(confs),
            predicted_count=len(predicted),
            per_char_prediction=tuple(predicted),
        )


class TemplateCharFallbackClassifier:
    """Fast character fallback classifier based on normalized template matching."""

    def __init__(self, *, charset: str, templates: np.ndarray, input_size: int = 24) -> None:
        self.charset = charset
        self.templates = templates.astype(np.float32, copy=False)
        self.input_size = int(input_size)

    @property
    def is_available(self) -> bool:
        return bool(self.charset) and self.templates.size > 0

    @classmethod
    def from_artifact_dir(cls, artifact_dir: Path) -> "TemplateCharFallbackClassifier | None":
        charset_file = artifact_dir / "charset.json"
        templates_file = artifact_dir / "templates.npz"
        if not charset_file.exists():
            return None
        payload = json.loads(charset_file.read_text(encoding="utf-8"))
        charset = str(payload.get("charset") or "")
        if not charset:
            return None

        input_size = int(payload.get("input_size") or 24)
        if templates_file.exists():
            data = np.load(templates_file)
            arr = np.asarray(data["templates"], dtype=np.float32)
            if arr.shape[0] != len(charset):
                return None
            return cls(charset=charset, templates=arr, input_size=input_size)

        templates = _render_default_templates(charset=charset, input_size=input_size)
        return cls(charset=charset, templates=templates, input_size=input_size)

    def predict(self, line_image: np.ndarray, slices: tuple[CharSlice, ...]) -> CharFallbackPrediction:
        if not slices or not self.is_available:
            return CharFallbackPrediction(text="", confidence=0.0, per_char_confidence=(), predicted_count=0)

        gray = _to_gray(line_image)
        predicted: list[str] = []
        confidences: list[float] = []
        for char_slice in slices:
            x1 = max(0, int(char_slice.x))
            y1 = max(0, int(char_slice.y))
            x2 = min(gray.shape[1], x1 + int(char_slice.width))
            y2 = min(gray.shape[0], y1 + int(char_slice.height))
            if x2 <= x1 or y2 <= y1:
                continue
            crop = gray[y1:y2, x1:x2]
            vec = _normalize_crop(crop, self.input_size)
            sims = self.templates @ vec
            idx = int(np.argmax(sims))
            best = float(sims[idx])
            predicted.append(self.charset[idx])
            confidences.append(max(0.0, min((best + 1.0) * 0.5, 1.0)))

        if not predicted:
            return CharFallbackPrediction(text="", confidence=0.0, per_char_confidence=(), predicted_count=0)
        aggregate = float(np.mean(confidences))
        return CharFallbackPrediction(
            text="".join(predicted),
            confidence=aggregate,
            per_char_confidence=tuple(confidences),
            predicted_count=len(predicted),
            per_char_prediction=tuple(predicted),
        )


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        return cv2.cvtColor(image[..., :3].astype(np.uint8, copy=False), cv2.COLOR_BGR2GRAY)
    raise ValueError(f"Unsupported line image shape: {image.shape}")


def _normalize_crop(crop: np.ndarray, input_size: int) -> np.ndarray:
    if crop.size == 0:
        crop = np.zeros((input_size, input_size), dtype=np.uint8)
    resized = cv2.resize(crop, (input_size, input_size), interpolation=cv2.INTER_AREA)
    inv = (255.0 - resized.astype(np.float32)) / 255.0
    vec = inv.reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-8:
        return vec
    return vec / norm


def _normalize_crop_for_cnn(crop: np.ndarray, input_size: int, mean: float, std: float) -> np.ndarray:
    if crop.size == 0:
        crop = np.zeros((input_size, input_size), dtype=np.uint8)
    resized = cv2.resize(crop, (input_size, input_size), interpolation=cv2.INTER_AREA)
    arr = resized.astype(np.float32) / 255.0
    arr = (arr - float(mean)) / float(std if abs(std) > 1e-8 else 1.0)
    return arr[np.newaxis, :, :]


def _render_default_templates(*, charset: str, input_size: int) -> np.ndarray:
    vectors: list[np.ndarray] = []
    for char in charset:
        canvas = np.ones((input_size, input_size), dtype=np.uint8) * 255
        cv2.putText(
            canvas,
            char,
            (2, int(input_size * 0.8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            0,
            2,
            cv2.LINE_AA,
        )
        vectors.append(_normalize_crop(canvas, input_size))
    return np.asarray(vectors, dtype=np.float32)
