from __future__ import annotations

from collections.abc import Sequence

from app.models.types import AiResult, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import BasePipeline, PipelineConfig, PipelineManager
from app.pipeline.echo_ocr_pipeline import (
    DEFAULT_CONTRAST_MODE,
    DEFAULT_FALLBACK_OCR_ENGINE,
    DEFAULT_OCR_ENGINE,
    DEFAULT_PARSER_MODE,
    DEFAULT_SCALE_ALGO,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_SEGMENTATION_MODE,
    DEFAULT_TARGET_LINE_HEIGHT_PX,
    EchoOcrPipeline,
)
from app.pipeline.measurement_parsers import LocalLlmMeasurementParser, LocalLlmParserConfig
from app.pipeline.ocr_engines import OcrEngine, build_engine


GUI_OCR_ENGINE_NAMES = ("glm-ocr", "surya", "paddleocr", "easyocr", "tesseract")
DEFAULT_GUI_OCR_ENGINE = DEFAULT_OCR_ENGINE
DEFAULT_GUI_PARSER_MODE = DEFAULT_PARSER_MODE
DEFAULT_GUI_SEGMENTATION_MODE = DEFAULT_SEGMENTATION_MODE
DEFAULT_GUI_TARGET_LINE_HEIGHT_PX = DEFAULT_TARGET_LINE_HEIGHT_PX
DEFAULT_GUI_MAX_FRAMES = 1
_GUI_OCR_FALLBACK_ORDER = ("surya", "paddleocr", "easyocr", "tesseract")


def _normalize_engine_names(engine_names: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_name in engine_names:
        name = str(raw_name).strip().lower()
        if not name or name in seen:
            continue
        if name not in GUI_OCR_ENGINE_NAMES:
            raise ValueError(f"Unsupported OCR engine for GUI manager: {raw_name}")
        normalized.append(name)
        seen.add(name)
    if not normalized:
        return (DEFAULT_GUI_OCR_ENGINE,)
    return tuple(normalized)


def _base_gui_parameters(
    *,
    ocr_engine_name: str,
    parser_mode: str,
    segmentation_mode: str,
    target_line_height_px: float,
    max_frames: int,
    panel_validation_mode: str = "off",
    vision_fallback_enabled: bool = False,
    panel_validation_model: str | None = None,
    panel_validation_command: str | None = None,
    vision_model: str | None = None,
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "ocr_engine": ocr_engine_name,
        "fallback_ocr_engine": DEFAULT_FALLBACK_OCR_ENGINE,
        "parser_mode": parser_mode,
        "scale_factor": DEFAULT_SCALE_FACTOR,
        "scale_algo": DEFAULT_SCALE_ALGO,
        "contrast_mode": DEFAULT_CONTRAST_MODE,
        "max_frames": max_frames,
        "segmentation_mode": segmentation_mode,
        "target_line_height_px": target_line_height_px,
        "panel_validation_mode": panel_validation_mode,
        "vision_fallback_enabled": vision_fallback_enabled,
        "study_companion_enabled": False,
        "strict_ocr_engine_selection": True,
    }
    if panel_validation_model is not None:
        parameters["panel_validation_model"] = panel_validation_model
    if panel_validation_command is not None:
        parameters["panel_validation_command"] = panel_validation_command
    if vision_model is not None:
        parameters["vision_model"] = vision_model
    return parameters


class GuiOcrComparisonPipeline(BasePipeline):
    name = "echo-ocr-comparison"

    def __init__(
        self,
        *,
        engine_names: Sequence[str],
        glm_ocr_engine: OcrEngine | None = None,
        surya_engine: OcrEngine | None = None,
        parser_mode: str = DEFAULT_GUI_PARSER_MODE,
        segmentation_mode: str = DEFAULT_GUI_SEGMENTATION_MODE,
        target_line_height_px: float = DEFAULT_GUI_TARGET_LINE_HEIGHT_PX,
        max_frames: int = DEFAULT_GUI_MAX_FRAMES,
        config: PipelineConfig | None = None,
    ) -> None:
        self._engine_names = _normalize_engine_names(engine_names)
        comparison_config = config or PipelineConfig(
            parameters={
                **_base_gui_parameters(
                    ocr_engine_name=self._engine_names[0],
                    parser_mode=parser_mode,
                    segmentation_mode=segmentation_mode,
                    target_line_height_px=target_line_height_px,
                    max_frames=max_frames,
                ),
                "selected_ocr_engines": list(self._engine_names),
                "comparison_mode": True,
            }
        )
        super().__init__(config=comparison_config)
        self._pipelines: dict[str, EchoOcrPipeline] = {
            engine_name: EchoOcrPipeline(
                ocr_engine=(
                    glm_ocr_engine
                    if engine_name == "glm-ocr" and glm_ocr_engine is not None
                    else surya_engine
                    if engine_name == "surya" and surya_engine is not None
                    else None
                ),
                config=PipelineConfig(
                    parameters=_base_gui_parameters(
                        ocr_engine_name=engine_name,
                        parser_mode=parser_mode,
                        segmentation_mode=segmentation_mode,
                        target_line_height_px=target_line_height_px,
                        max_frames=max_frames,
                    )
                ),
            )
            for engine_name in self._engine_names
        }

    def run(self, request: PipelineRequest) -> PipelineResult:
        primary_engine_name = self._engine_names[0]
        primary_result: PipelineResult | None = None
        first_success: PipelineResult | None = None
        comparison_rows: list[dict[str, object]] = []
        errors: list[str] = []

        for engine_name in self._engine_names:
            result = self._pipelines[engine_name].run(request)
            row: dict[str, object] = {
                "engine": engine_name,
                "status": result.status,
            }
            if result.ai_result is not None and result.status == "ok":
                ai_result = result.ai_result
                row.update(
                    {
                        "model_name": ai_result.model_name,
                        "measurements": [
                            {
                                "name": measurement.name,
                                "value": measurement.value,
                                "unit": measurement.unit or "",
                            }
                            for measurement in ai_result.measurements
                        ],
                        "exact_lines": list(ai_result.raw.get("exact_lines", []))
                        if isinstance(ai_result.raw.get("exact_lines"), list)
                        else [],
                        "line_predictions": list(ai_result.raw.get("line_predictions", []))
                        if isinstance(ai_result.raw.get("line_predictions"), list)
                        else [],
                    }
                )
                if first_success is None:
                    first_success = result
            else:
                error_message = result.error or "Unknown OCR failure"
                row["error"] = error_message
                errors.append(f"{engine_name}: {error_message}")
            comparison_rows.append(row)
            if engine_name == primary_engine_name:
                primary_result = result

        base_result = primary_result
        if base_result is None or base_result.status != "ok" or base_result.ai_result is None:
            base_result = first_success
        if base_result is None or base_result.ai_result is None:
            message = "; ".join(errors) if errors else "All selected OCR engines failed."
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="error",
                ai_result=None,
                error=message,
            )

        base_ai_result = base_result.ai_result
        raw = dict(base_ai_result.raw)
        raw.update(
            {
                "comparison_mode": True,
                "selected_ocr_engines": list(self._engine_names),
                "primary_ocr_engine": primary_engine_name,
                "engine_comparison": comparison_rows,
            }
        )
        return PipelineResult(
            dicom_path=request.dicom_path,
            status="ok",
            ai_result=AiResult(
                model_name=f"{base_ai_result.model_name} [compare]",
                created_at=base_ai_result.created_at,
                boxes=list(base_ai_result.boxes),
                measurements=list(base_ai_result.measurements),
                raw=raw,
            ),
            error=None,
        )


def _resolve_engine_with_guardrails(
    *,
    ocr_engine_name: str,
    glm_ocr_engine: OcrEngine | None = None,
    surya_engine: OcrEngine | None = None,
) -> tuple[OcrEngine, str, str | None]:
    normalized_name = str(ocr_engine_name).strip().lower() or DEFAULT_GUI_OCR_ENGINE

    def _build_named_engine(name: str) -> OcrEngine:
        if name == "glm-ocr" and glm_ocr_engine is not None:
            return glm_ocr_engine
        if name == "surya" and surya_engine is not None:
            return surya_engine
        return build_engine(name)

    try:
        return _build_named_engine(normalized_name), normalized_name, None
    except Exception as primary_exc:
        if normalized_name != "glm-ocr":
            raise

        fallback_errors: list[str] = []
        for fallback_name in _GUI_OCR_FALLBACK_ORDER:
            try:
                fallback_engine = _build_named_engine(fallback_name)
            except Exception as fallback_exc:
                fallback_errors.append(f"{fallback_name}: {fallback_exc}")
                continue
            warning = (
                "GLM-OCR was unavailable; falling back to "
                f"{fallback_name}. "
                "You can fix GLM startup with GLM_OCR_ENV/GLM_OCR_RUNNER or select another engine in the GUI. "
                f"GLM error: {primary_exc}"
            )
            return fallback_engine, fallback_name, warning

        fallback_details = "; ".join(fallback_errors) if fallback_errors else "no fallback engine started"
        raise RuntimeError(
            "GLM-OCR startup failed and no fallback OCR engine could be loaded. "
            "Check GLM_OCR_ENV/GLM_OCR_RUNNER and OCR dependencies. "
            f"GLM error: {primary_exc}. Fallback attempts: {fallback_details}"
        ) from primary_exc


def build_gui_ocr_manager(
    *,
    ocr_engine_name: str = DEFAULT_GUI_OCR_ENGINE,
    glm_ocr_engine: OcrEngine | None = None,
    surya_engine: OcrEngine | None = None,
    parser_mode: str = DEFAULT_GUI_PARSER_MODE,
    segmentation_mode: str = DEFAULT_GUI_SEGMENTATION_MODE,
    target_line_height_px: float = DEFAULT_GUI_TARGET_LINE_HEIGHT_PX,
    max_frames: int = DEFAULT_GUI_MAX_FRAMES,
) -> PipelineManager:
    normalized_name = _normalize_engine_names((ocr_engine_name,))[0]
    resolved_engine, resolved_engine_name, startup_warning = _resolve_engine_with_guardrails(
        ocr_engine_name=normalized_name,
        glm_ocr_engine=glm_ocr_engine,
        surya_engine=surya_engine,
    )

    parameters = _base_gui_parameters(
        ocr_engine_name=resolved_engine_name,
        parser_mode=parser_mode,
        segmentation_mode=segmentation_mode,
        target_line_height_px=target_line_height_px,
        max_frames=max_frames,
    )
    if startup_warning:
        parameters["startup_warning"] = startup_warning
        parameters["requested_ocr_engine"] = normalized_name
        parameters["strict_ocr_engine_selection"] = False

    pipeline = EchoOcrPipeline(
        ocr_engine=resolved_engine,
        config=PipelineConfig(
            parameters=parameters
        ),
    )

    manager = PipelineManager()
    manager.register(pipeline)
    manager.set_active(pipeline.name)
    return manager


def build_gui_ocr_comparison_manager(
    *,
    ocr_engine_names: Sequence[str],
    glm_ocr_engine: OcrEngine | None = None,
    surya_engine: OcrEngine | None = None,
    parser_mode: str = DEFAULT_GUI_PARSER_MODE,
    segmentation_mode: str = DEFAULT_GUI_SEGMENTATION_MODE,
    target_line_height_px: float = DEFAULT_GUI_TARGET_LINE_HEIGHT_PX,
    max_frames: int = DEFAULT_GUI_MAX_FRAMES,
) -> PipelineManager:
    pipeline = GuiOcrComparisonPipeline(
        engine_names=ocr_engine_names,
        glm_ocr_engine=glm_ocr_engine,
        surya_engine=surya_engine,
        parser_mode=parser_mode,
        segmentation_mode=segmentation_mode,
        target_line_height_px=target_line_height_px,
        max_frames=max_frames,
    )
    manager = PipelineManager()
    manager.register(pipeline)
    manager.set_active(pipeline.name)
    return manager


def build_validation_manager(
    *,
    glm_ocr_engine: OcrEngine | None = None,
    surya_engine: OcrEngine | None = None,
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M",
    llm_command: str = "ollama",
    parser_mode: str = "local_llm",
    vision_model: str = "qwen2.5vl:3b-q4_K_M",
    vision_fallback_enabled: bool = True,
) -> PipelineManager:
    engine, resolved_engine_name, startup_warning = _resolve_engine_with_guardrails(
        ocr_engine_name=DEFAULT_GUI_OCR_ENGINE,
        glm_ocr_engine=glm_ocr_engine,
        surya_engine=surya_engine,
    )
    parser = LocalLlmMeasurementParser(
        config=LocalLlmParserConfig(
            model=llm_model,
            command=llm_command,
            timeout_s=30.0,
        )
    )
    if parser_mode == "regex_then_llm":
        from app.pipeline.measurement_parsers import RegexMeasurementParser, RegexThenLlmMeasurementParser

        parser = RegexThenLlmMeasurementParser(
            regex_parser=RegexMeasurementParser(),
            llm_parser=parser,
        )
    parameters = _base_gui_parameters(
        ocr_engine_name=resolved_engine_name,
        parser_mode=parser_mode,
        segmentation_mode=DEFAULT_GUI_SEGMENTATION_MODE,
        target_line_height_px=DEFAULT_GUI_TARGET_LINE_HEIGHT_PX,
        max_frames=DEFAULT_GUI_MAX_FRAMES,
        panel_validation_mode="selective",
        vision_fallback_enabled=vision_fallback_enabled,
        panel_validation_model=llm_model,
        panel_validation_command=llm_command,
        vision_model=vision_model,
    )
    if startup_warning:
        parameters["startup_warning"] = startup_warning
        parameters["requested_ocr_engine"] = DEFAULT_GUI_OCR_ENGINE
        parameters["strict_ocr_engine_selection"] = False

    pipeline = EchoOcrPipeline(
        ocr_engine=engine,
        parser=parser,
        config=PipelineConfig(
            parameters=parameters
        ),
    )

    manager = PipelineManager()
    manager.register(pipeline)
    manager.set_active(pipeline.name)
    return manager
