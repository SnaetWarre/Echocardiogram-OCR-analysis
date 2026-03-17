from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.pipeline.ocr_engines import SuryaOcrEngine


@dataclass
class StartupServices:
    surya_engine: SuryaOcrEngine | None = None
    managed_ollama_process: subprocess.Popen[str] | None = None


class ServiceProcessManager:
    def __init__(
        self,
        *,
        ai_enabled: bool,
        ollama_health_url: str = "http://127.0.0.1:11434/api/tags",
        startup_timeout_s: float = 45.0,
    ) -> None:
        self._ai_enabled = ai_enabled
        self._ollama_health_url = ollama_health_url
        self._startup_timeout_s = startup_timeout_s

    def initialize(self, on_progress: Callable[[str, int, int], None]) -> StartupServices:
        if not self._ai_enabled:
            on_progress("AI services disabled.", 1, 1)
            return StartupServices()

        on_progress("Checking Ollama service...", 1, 3)
        managed_ollama = self._ensure_ollama_running()

        on_progress("Loading Surya models...", 2, 3)
        surya_engine = self._ensure_surya_worker()

        on_progress("Ready!", 3, 3)
        return StartupServices(
            surya_engine=surya_engine,
            managed_ollama_process=managed_ollama,
        )

    def _ensure_ollama_running(self) -> subprocess.Popen[str] | None:
        if self._is_ollama_healthy():
            return None

        if shutil.which("ollama") is None:
            raise RuntimeError(
                "Ollama CLI was not found in PATH. Install Ollama and retry."
            )

        process = subprocess.Popen(
            ["ollama", "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        if self._wait_for_ollama():
            return process

        self._terminate_process(process)
        raise RuntimeError(
            "Ollama did not become healthy in time. Check that port 11434 is available "
            "and run `ollama serve` manually for diagnostics."
        )

    def _wait_for_ollama(self) -> bool:
        started = time.monotonic()
        while (time.monotonic() - started) < self._startup_timeout_s:
            if self._is_ollama_healthy():
                return True
            time.sleep(0.5)
        return False

    def _is_ollama_healthy(self) -> bool:
        request = Request(self._ollama_health_url, method="GET")
        try:
            with urlopen(request, timeout=2.0) as response:
                status = getattr(response, "status", 200)
                return int(status) < 500
        except (TimeoutError, URLError, ValueError):
            return False

    @staticmethod
    def _ensure_surya_worker() -> SuryaOcrEngine:
        try:
            return SuryaOcrEngine()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Surya startup failed because the required executable was not found. "
                "Ensure mamba/conda is installed and the surya environment exists, "
                "or set SURYA_RUNNER=python to use the current Python."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Surya startup failed: {exc}") from exc

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    @staticmethod
    def shutdown_managed_ollama(process: subprocess.Popen[str] | None) -> None:
        if process is None:
            return
        if process.poll() is not None:
            return
        ServiceProcessManager._terminate_process(process)

    @staticmethod
    def troubleshooting_text() -> str:
        return (
            "Troubleshooting:\n"
            "1) Confirm `ollama` is installed and `ollama serve` runs.\n"
            "2) Confirm the Surya environment exists (mamba/conda env list).\n"
            "3) Ensure the worker can run. Auto-detects mamba, conda, micromamba;\n"
            "   else uses current Python. Override with SURYA_RUNNER, SURYA_ENV.\n"
        )
