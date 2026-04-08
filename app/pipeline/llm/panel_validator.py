from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from app.models.types import AiMeasurement
from app.pipeline.transcription.line_transcriber import PanelTranscription
from app.pipeline.measurements.measurement_parsers import parse_json_payload, postprocess_measurements, run_local_model


@dataclass(frozen=True)
class PanelValidatorConfig:
    model: str = "qwen2.5:7b-instruct-q4_K_M"
    command: str = "ollama"
    timeout_s: float = 30.0
    mode: str = "selective"
    min_uncertain_lines: int = 1
    min_fallback_invocations: int = 1
    min_engine_disagreements: int = 1


@dataclass(frozen=True)
class PanelValidationResult:
    measurements: tuple[AiMeasurement, ...] = ()
    applied: bool = False
    reason: str = ""
    raw_response: str = ""


class LocalLlmPanelValidator:
    def __init__(
        self,
        config: PanelValidatorConfig | None = None,
        *,
        runner: Callable[[str], str] | None = None,
    ) -> None:
        self.config = config or PanelValidatorConfig()
        self._runner = runner

    def should_run(self, panel: PanelTranscription, measurements: list[AiMeasurement]) -> bool:
        mode = self.config.mode.strip().lower()
        if mode in {"", "off", "disabled", "0", "false", "no"}:
            return False
        if not panel.lines:
            return False
        if mode == "always":
            return True
        if mode not in {"selective", "auto"}:
            return False
        if not measurements:
            return True
        if panel.uncertain_line_count >= self.config.min_uncertain_lines:
            return True
        if panel.fallback_invocations >= self.config.min_fallback_invocations:
            return True
        if panel.engine_disagreement_count >= self.config.min_engine_disagreements:
            return True
        return False

    def validate(
        self,
        panel: PanelTranscription,
        measurements: list[AiMeasurement],
        *,
        confidence: float,
    ) -> PanelValidationResult:
        if not self.should_run(panel, measurements):
            return PanelValidationResult(applied=False, reason="skipped")

        prompt = self._build_prompt(panel, measurements)
        try:
            raw_response = self._run_model(prompt)
        except Exception as exc:
            return PanelValidationResult(applied=False, reason=f"model_error:{exc}")

        refined = self._parse_measurements(raw_response, confidence=confidence)
        if not refined:
            return PanelValidationResult(applied=False, reason="empty_response", raw_response=raw_response)
        return PanelValidationResult(
            measurements=tuple(refined),
            applied=True,
            reason="accepted",
            raw_response=raw_response,
        )

    def _build_prompt(self, panel: PanelTranscription, measurements: list[AiMeasurement]) -> str:
        indexed_lines = [
            {
                "order": line.order + 1,
                "text": line.text,
                "confidence": round(float(line.confidence), 3),
                "uncertain": bool(line.uncertain),
            }
            for line in panel.lines
            if line.text.strip()
        ]
        seed_measurements = [
            {
                "order": (item.order_hint + 1) if item.order_hint is not None else None,
                "name": item.name,
                "value": item.value,
                "unit": item.unit or "",
            }
            for item in measurements
        ]
        return (
            "You validate echocardiogram measurement extraction from OCR panel lines.\n"
            "Return ONLY valid JSON with this shape:\n"
            '{"measurements":[{"order":1,"name":"","value":"","unit":""}]}\n'
            "Rules:\n"
            "- Use the OCR lines as the source of truth.\n"
            "- Keep labels as literally as possible.\n"
            "- Keep the 1-based line order for each measurement whenever possible.\n"
            "- Ignore telemetry, UI chrome, and decorative noise.\n"
            "- value must be numeric text only.\n"
            "- unit must be one of: %, mmHg, ml/m2, m/s2, cm2, cm/s, m/s, bpm, cm, mm, ms, ml, s, or empty string.\n"
            "- If a line is not a measurement, omit it.\n"
            "- Prefer fixing ambiguous labels/units over inventing new values.\n\n"
            "OCR lines JSON:\n"
            f"{json.dumps(indexed_lines, ensure_ascii=True)}\n\n"
            "Current parsed measurements JSON:\n"
            f"{json.dumps(seed_measurements, ensure_ascii=True)}\n"
        )

    def _run_model(self, prompt: str) -> str:
        if self._runner is not None:
            return self._runner(prompt)
        return run_local_model(
            command=self.config.command,
            model=self.config.model,
            prompt=prompt,
            timeout_s=self.config.timeout_s,
        )

    @staticmethod
    def _parse_measurements(payload: str, *, confidence: float) -> list[AiMeasurement]:
        parsed = parse_json_payload(payload)
        rows_obj = parsed.get("measurements") if isinstance(parsed, dict) else parsed
        if not isinstance(rows_obj, list):
            return []

        items: list[AiMeasurement] = []
        for fallback_order, row in enumerate(rows_obj):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip()
            value = str(row.get("value", "")).strip().replace(",", ".")
            unit = str(row.get("unit", "")).strip() or None
            order_hint = LocalLlmPanelValidator._parse_order_hint(row.get("order"), fallback_order=fallback_order)
            if not name or not value:
                continue
            items.append(
                AiMeasurement(
                    name=name,
                    value=value,
                    unit=unit,
                    source=f"panel_validator:{confidence:.3f}",
                    order_hint=order_hint,
                )
            )
        return postprocess_measurements(items)

    @staticmethod
    def _parse_order_hint(raw_order: object, *, fallback_order: int) -> int:
        try:
            parsed = int(raw_order)
        except (TypeError, ValueError):
            return fallback_order
        return max(0, parsed - 1)
