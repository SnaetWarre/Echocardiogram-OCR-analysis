from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import cv2
import numpy as np


def _resolve_surya_worker_cmd(worker_script: Path) -> list[str]:
    """
    Build the command to run the Surya worker, auto-detecting the environment runner.
    Prefers mamba, then conda, then falls back to the current Python interpreter.
    """
    env_name = os.getenv("SURYA_ENV", "surya").strip()
    runner_override = os.getenv("SURYA_RUNNER", "").strip().lower()

    if runner_override == "python":
        return [sys.executable, str(worker_script)]

    if runner_override in ("mamba", "conda", "micromamba"):
        runner = shutil.which(runner_override)
        if runner:
            return [runner, "run", "-n", env_name, "python", str(worker_script)]
        raise UnavailableOcrEngineError(
            f"SURYA_RUNNER={runner_override} but '{runner_override}' not found in PATH."
        )

    # Auto-detect: mamba first, then conda
    for runner_name in ("mamba", "conda", "micromamba"):
        runner = shutil.which(runner_name)
        if runner:
            return [runner, "run", "-n", env_name, "python", str(worker_script)]

    # Fallback: run with current Python (surya must be installed in this env)
    return [sys.executable, str(worker_script)]


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


class SuryaOcrEngine:
    name = "surya"

    def __init__(self) -> None:
        self._worker_process: Optional[subprocess.Popen] = None
        self._start_worker()

    def _start_worker(self) -> None:
        if self._worker_process is not None:
            self._stop_worker()

        worker_script = Path(__file__).parent / "surya_worker.py"
        cmd = _resolve_surya_worker_cmd(worker_script)

        # Start process with piped stdin/stdout
        self._worker_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,  # Text mode for easier JSON line reading
            bufsize=1,  # Line buffered
        )
        
        # Wait for readiness signal
        start_time = time.time()
        while time.time() - start_time < 30:  # 30 second timeout for model loading
            line = self._worker_process.stdout.readline()
            if not line:
                # Process exited pre-maturely
                self._check_process()
                continue
                
            try:
                data = json.loads(line)
                if data.get("status") == "ready":
                    return # Worker is ready
                if "error" in data:
                    raise UnavailableOcrEngineError(f"Surya worker failed to start: {data['error']}")
            except json.JSONDecodeError:
                pass # Ignore non-JSON output during startup warnings
                
        raise UnavailableOcrEngineError("Surya worker startup timed out after 30 seconds")

    def _stop_worker(self) -> None:
        if self._worker_process:
            if self._worker_process.stdin:
                self._worker_process.stdin.close()
            self._worker_process.terminate()
            try:
                self._worker_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._worker_process.kill()
            self._worker_process = None

    def _check_process(self) -> None:
        if self._worker_process is None or self._worker_process.poll() is not None:
            print("Surya worker subprocess died. Restarting...")
            self._start_worker()

    def extract(self, image: np.ndarray) -> OcrResult:
        self._check_process()
        
        # Encode image to base64 PNG. cv2.imencode handles gray/BGR natively.
        success, encoded_image = cv2.imencode('.png', image)
        if not success:
            raise RuntimeError("Failed to encode image for Surya worker")
            
        b64_string = base64.b64encode(encoded_image).decode('utf-8')
        req_id = str(uuid.uuid4())
        
        payload = json.dumps({
            "id": req_id,
            "image_base64": b64_string
        })
        
        # Send payload
        try:
            self._worker_process.stdin.write(payload + "\n")
            self._worker_process.stdin.flush()
        except BrokenPipeError:
            self._check_process()
            self._worker_process.stdin.write(payload + "\n")
            self._worker_process.stdin.flush()
            
        # Read response
        while True:
            line = self._worker_process.stdout.readline()
            if not line:
                self._check_process()
                raise RuntimeError("Surya worker disconnected unexpectedly")
                
            line = line.strip()
            if not line:
                continue
                
            try:
                res = json.loads(line)
                if res.get("id") == req_id:
                    if "error" in res:
                        print(f"Surya error: {res['error']}")
                        print(f"Traceback: {res.get('traceback', '')}")
                        return OcrResult(text="", confidence=0.0, tokens=[], engine_name=self.name)
                        
                    return OcrResult(
                        text=res.get("text", ""),
                        confidence=res.get("confidence", 0.0),
                        tokens=[], # We don't really need token-level confidence for the current architecture
                        engine_name=self.name
                    )
                else:
                    print(f"Warning: Discarded mismatched Surya response (expected {req_id}, got {res.get('id')})")
            except json.JSONDecodeError:
                # Mamba/conda might print warnings to stdout occasionally
                print(f"Surya worker non-JSON output: {line}")

    def __del__(self):
        self._stop_worker()

def build_engine(name: str) -> OcrEngine:
    lowered = name.strip().lower()
    if lowered == "tesseract":
        return TesseractEngine()
    if lowered == "easyocr":
        return EasyOcrEngine()
    if lowered == "paddleocr":
        return PaddleOcrEngine()
    if lowered == "surya":
        return SuryaOcrEngine()
    raise ValueError(f"Unsupported OCR engine: {name}")
