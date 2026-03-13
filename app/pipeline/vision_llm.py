from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from app.pipeline.measurement_decoder import canonicalize_exact_line
from app.pipeline.measurement_parsers import parse_json_payload


@dataclass(frozen=True)
class VisionLineExpertConfig:
    model: str = "qwen2.5-vl:7b"
    ollama_url: str = "http://127.0.0.1:11434"
    timeout_s: float = 20.0


@dataclass(frozen=True)
class VisionLineExpertResult:
    text: str
    confidence: float
    raw_response: str = ""


class VisionLineExpert(Protocol):
    name: str

    def transcribe(self, image: np.ndarray, *, candidate_hints: Sequence[str] | None = None) -> VisionLineExpertResult: ...


class OllamaVisionLineExpert:
    name = "ollama-vision"

    def __init__(self, config: VisionLineExpertConfig | None = None) -> None:
        self.config = config or VisionLineExpertConfig()

    def transcribe(self, image: np.ndarray, *, candidate_hints: Sequence[str] | None = None) -> VisionLineExpertResult:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Failed to encode line crop for vision fallback.")
        prompt = self._build_prompt(candidate_hints or ())
        payload = json.dumps(
            {
                "model": self.config.model,
                "prompt": prompt,
                "images": [base64.b64encode(encoded).decode("utf-8")],
                "stream": False,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.config.ollama_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Vision fallback request failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Vision fallback request failed: {exc}") from exc

        raw_response = str(body.get("response", "") or "").strip()
        text = self._extract_line_text(raw_response)
        confidence = self._estimate_confidence(text, candidate_hints or ())
        return VisionLineExpertResult(text=text, confidence=confidence, raw_response=raw_response)

    @staticmethod
    def _build_prompt(candidate_hints: Sequence[str]) -> str:
        hints = [canonicalize_exact_line(item) for item in candidate_hints if canonicalize_exact_line(item)]
        hints_block = ""
        if hints:
            hints_block = (
                "OCR candidate hints from other engines/views (may be wrong):\n"
                + "\n".join(f"- {item}" for item in hints[:4])
                + "\n\n"
            )
        return (
            "Transcribe the single echocardiography measurement line shown in the image.\n"
            "Return ONLY valid JSON with one key: {\"line_text\": \"...\"}.\n"
            "Rules:\n"
            "- Preserve the displayed measurement label as literally as possible.\n"
            "- Keep a real leading numeric prefix like 1, 2, 3 if it belongs to the displayed line.\n"
            "- Include the numeric value and unit exactly once.\n"
            "- Do not explain your answer.\n\n"
            f"{hints_block}"
        )

    @staticmethod
    def _extract_line_text(payload: str) -> str:
        parsed = parse_json_payload(payload)
        if isinstance(parsed, dict):
            line_text = str(parsed.get("line_text", "") or "").strip()
            if line_text:
                return canonicalize_exact_line(line_text)
        return canonicalize_exact_line(payload)

    @staticmethod
    def _estimate_confidence(text: str, candidate_hints: Sequence[str]) -> float:
        if not text:
            return 0.0
        canonical_hints = {canonicalize_exact_line(item) for item in candidate_hints if canonicalize_exact_line(item)}
        if text in canonical_hints:
            return 0.9
        return 0.82 if canonical_hints else 0.78
