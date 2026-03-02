from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class OcrToken:
    text: str
    confidence: float


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    tokens: list[OcrToken]
    engine_name: str


class OcrEngine(Protocol):
    name: str

    def extract(self, image: np.ndarray) -> OcrResult: ...


class UnavailableOcrEngineError(RuntimeError):
    pass


class TesseractEngine:
    name = "tesseract"

    def __init__(self, psm: int = 6) -> None:
        self.psm = psm
        try:
            import pytesseract  # type: ignore

            tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            elif shutil.which("tesseract") is None:
                local_tesseract = Path(sys.executable).resolve().parent / "tesseract"
                if local_tesseract.exists():
                    pytesseract.pytesseract.tesseract_cmd = str(local_tesseract)
            self._pytesseract = pytesseract
        except Exception as exc:
            raise UnavailableOcrEngineError("pytesseract is not installed") from exc

    def extract(self, image: np.ndarray) -> OcrResult:
        pytesseract = self._pytesseract
        cfg = f"--oem 3 --psm {self.psm}"
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            config=cfg,
        )
        texts = []
        tokens: list[OcrToken] = []
        for idx, raw in enumerate(data.get("text", [])):
            text = str(raw).strip()
            if not text:
                continue
            conf_raw = data.get("conf", ["-1"])[idx]
            try:
                conf = max(float(conf_raw), 0.0) / 100.0
            except Exception:
                conf = 0.0
            texts.append(text)
            tokens.append(OcrToken(text=text, confidence=conf))
        confidence = float(sum(t.confidence for t in tokens) / len(tokens)) if tokens else 0.0
        return OcrResult(
            text="\n".join(texts),
            confidence=confidence,
            tokens=tokens,
            engine_name=self.name,
        )


class EasyOcrEngine:
    name = "easyocr"

    def __init__(self, langs: list[str] | None = None, gpu: bool = False) -> None:
        try:
            import easyocr  # type: ignore

            self._reader = easyocr.Reader(langs or ["en"], gpu=gpu, verbose=False)
        except Exception as exc:
            raise UnavailableOcrEngineError(f"easyocr unavailable: {exc}") from exc

    def extract(self, image: np.ndarray) -> OcrResult:
        rows = self._reader.readtext(image, detail=1, paragraph=False)
        tokens: list[OcrToken] = []
        lines: list[str] = []
        for row in rows:
            if len(row) < 3:
                continue
            text = str(row[1]).strip()
            if not text:
                continue
            conf = float(max(min(row[2], 1.0), 0.0))
            tokens.append(OcrToken(text=text, confidence=conf))
            lines.append(text)
        confidence = float(sum(t.confidence for t in tokens) / len(tokens)) if tokens else 0.0
        return OcrResult(
            text="\n".join(lines),
            confidence=confidence,
            tokens=tokens,
            engine_name=self.name,
        )


class PaddleOcrEngine:
    name = "paddleocr"

    def __init__(self, lang: str = "en", use_gpu: bool = False) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore

            # Avoid repeated online host checks when local model files exist.
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            # PaddleOCR constructor differs across versions. show_log removed in some releases.
            try:
                self._ocr = PaddleOCR(use_angle_cls=False, lang=lang, show_log=False)
            except Exception as e:
                if "show_log" in str(e) or "Unknown argument" in str(e):
                    self._ocr = PaddleOCR(use_angle_cls=False, lang=lang)
                else:
                    raise
        except Exception as exc:
            raise UnavailableOcrEngineError(f"paddleocr unavailable: {exc}") from exc

    def extract(self, image: np.ndarray) -> OcrResult:
        rows = self._ocr.ocr(image, cls=False)
        tokens: list[OcrToken] = []
        lines: list[str] = []
        for group in rows or []:
            for item in group or []:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                text_conf = item[1]
                if not isinstance(text_conf, tuple) or len(text_conf) < 2:
                    continue
                text = str(text_conf[0]).strip()
                if not text:
                    continue
                conf = float(max(min(float(text_conf[1]), 1.0), 0.0))
                tokens.append(OcrToken(text=text, confidence=conf))
                lines.append(text)
        confidence = float(sum(t.confidence for t in tokens) / len(tokens)) if tokens else 0.0
        return OcrResult(
            text="\n".join(lines),
            confidence=confidence,
            tokens=tokens,
            engine_name=self.name,
        )


def build_engine(name: str) -> OcrEngine:
    lowered = name.strip().lower()
    if lowered == "tesseract":
        return TesseractEngine()
    if lowered == "easyocr":
        return EasyOcrEngine()
    if lowered == "paddleocr":
        return PaddleOcrEngine()
    raise ValueError(f"Unsupported OCR engine: {name}")
