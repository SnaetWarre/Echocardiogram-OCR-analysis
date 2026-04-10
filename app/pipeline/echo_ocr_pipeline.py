from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import AiMeasurement, AiResult, DicomSeries, OverlayBox, PipelineRequest, PipelineResult
from app.ocr.preprocessing import (
    DEFAULT_CONTRAST_MODE,
    DEFAULT_SCALE_ALGO,
    DEFAULT_SCALE_FACTOR,
    preprocess_roi,
)
from app.pipeline.ai_pipeline import BasePipeline, PipelineConfig
from app.pipeline.layout.echo_ocr_box_detector import (
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
)
from app.pipeline.measurements.line_first_parser import LineFirstParser
from app.pipeline.layout.line_segmenter import LineSegmenter, SegmentationResult
from app.pipeline.transcription.line_transcriber import LineTranscriber, PanelTranscription
from app.pipeline.lexicon.lexicon_builder import LexiconArtifact, build_lexicon_artifact
from app.pipeline.lexicon.lexicon_reranker import LexiconReranker
from app.pipeline.measurements.measurement_decoder import (
    apply_safe_measurement_corrections,
    canonicalize_exact_line,
    parse_measurement_line,
)
from app.pipeline.output.echo_ocr_schema import MeasurementRecord
from app.pipeline.output.echo_sidecar_writer import SidecarWriter
from app.pipeline.ocr.ocr_engines import OcrEngine, OcrResult, OcrToken, build_engine
from app.pipeline.llm.panel_validator import LocalLlmPanelValidator, PanelValidatorConfig
from app.pipeline.measurements.study_companion_discovery import StudyCompanionDiscovery
from app.repo_paths import DEFAULT_OCR_REDESIGN_LEXICON_PATH


DEFAULT_OCR_ENGINE = "glm-ocr"
DEFAULT_FALLBACK_OCR_ENGINE = "surya"
DEFAULT_SEGMENTATION_MODE = "adaptive"
DEFAULT_TARGET_LINE_HEIGHT_PX = 20.0
DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX = 16
DEFAULT_PREPROCESS_PROFILE = "sweep_gray_x3_lanczos"

DEFAULT_LEXICON_PATH = DEFAULT_OCR_REDESIGN_LEXICON_PATH
MEASUREMENT_BOX_RGB = (0x1A, 0x21, 0x29)


class MeasurementBoxDetector(Protocol):
    def detect(self, frame: np.ndarray) -> RoiDetection: ...


class NoopOcrEngine:
    name = "noop-ocr"

    def extract(self, image: np.ndarray) -> OcrResult:
        return OcrResult(text="", confidence=0.0, tokens=[], engine_name=self.name)


class RoutedOcrEngine:
    def __init__(self, primary: OcrEngine, fallback: OcrEngine | None = None) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name if fallback is None else f"{primary.name}+{fallback.name}"

    def extract(self, image: np.ndarray) -> OcrResult:
        return self.primary.extract(image)


def _scout_tokens_useful(result: OcrResult) -> bool:
    return any(str(getattr(token, "text", "") or "").strip() for token in (result.tokens or ()))


@dataclass(frozen=True)
class _ParseSourceInfo:
    parser_source: str
    source_kind: str = "pixel_ocr"
    source_path: str = ""
    source_modality: str = ""
    source_note: str = ""


class EchoOcrPipeline(BasePipeline):
    name = "echo-ocr"
    version = "v2-line-first"

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None = None,
        box_detector: MeasurementBoxDetector | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        parameters = dict(self.config.parameters)
        self._provided_ocr_engine = ocr_engine
        self._default_engine = (
            str(parameters.get("ocr_engine", os.getenv("ECHO_OCR_ENGINE", DEFAULT_OCR_ENGINE)))
            .strip()
            .lower()
        )
        self._requested_engine = (
            str(parameters.get("requested_ocr_engine", self._default_engine))
            .strip()
            .lower()
        )
        self._startup_warning = str(parameters.get("startup_warning", "")).strip()
        self._scale_factor = self._read_int_parameter(parameters, "scale_factor", default=DEFAULT_SCALE_FACTOR)
        self._scale_algo = str(parameters.get("scale_algo", DEFAULT_SCALE_ALGO)).strip().lower()
        self._contrast_mode = str(parameters.get("contrast_mode", DEFAULT_CONTRAST_MODE)).strip().lower()
        self._segmentation_mode = str(parameters.get("segmentation_mode", DEFAULT_SEGMENTATION_MODE)).strip().lower()
        self._target_line_height_px = self._read_float_parameter(
            parameters,
            "target_line_height_px",
            default=DEFAULT_TARGET_LINE_HEIGHT_PX,
        )
        self._preprocess_profile = str(
            parameters.get("preprocess_profile", DEFAULT_PREPROCESS_PROFILE)
        ).strip().lower()
        self._segmentation_extra_left_pad_px = self._read_int_parameter(
            parameters,
            "segmentation_extra_left_pad_px",
            default=DEFAULT_SEGMENTATION_EXTRA_LEFT_PAD_PX,
        )
        self._strict_ocr_engine_selection = self._read_bool_parameter(
            parameters,
            "strict_ocr_engine_selection",
            default=False,
        )
        self._fallback_engine_name = str(
            parameters.get(
                "fallback_ocr_engine",
                os.getenv("ECHO_OCR_FALLBACK_ENGINE", DEFAULT_FALLBACK_OCR_ENGINE),
            )
        ).strip().lower()
        self._lexicon_path = Path(str(parameters.get("lexicon_path", DEFAULT_LEXICON_PATH))).expanduser()
        self._segmentation_debug_dir = str(parameters.get("segmentation_debug_dir", "")).strip()
        self._save_segmentation_debug = (
            str(parameters.get("save_segmentation_debug", "0")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self._study_companion_enabled = self._read_bool_parameter(
            parameters,
            "study_companion_enabled",
            default=str(os.getenv("ECHO_STUDY_COMPANION_ENABLED", "0")).strip().lower()
            in {"1", "true", "yes", "on"},
        )
        self._study_companion_recursive = self._read_bool_parameter(
            parameters,
            "study_companion_recursive",
            default=str(os.getenv("ECHO_STUDY_COMPANION_RECURSIVE", "1")).strip().lower()
            in {"1", "true", "yes", "on"},
        )
        self._study_companion_max_files = self._read_int_parameter(parameters, "study_companion_max_files", default=256)
        self._panel_validation_mode = str(
            parameters.get("panel_validation_mode", os.getenv("ECHO_PANEL_VALIDATION_MODE", "off"))
        ).strip().lower()
        self._panel_validation_model = str(
            parameters.get("panel_validation_model", os.getenv("ECHO_PANEL_VALIDATION_MODEL", "qwen2.5:7b-instruct-q4_K_M"))
        ).strip()
        self._panel_validation_command = str(
            parameters.get("panel_validation_command", os.getenv("ECHO_PANEL_VALIDATION_COMMAND", "ollama"))
        ).strip()
        self._panel_validation_timeout_s = self._read_float_parameter(
            parameters,
            "panel_validation_timeout_s",
            default=30.0,
        )
        self.ocr_engine: OcrEngine = NoopOcrEngine()
        self._components_ready = False
        self.box_detector = box_detector or TopLeftBlueGrayBoxDetector()
        self._fallback_ocr_engine: OcrEngine | None = None
        self._study_companion_discovery: StudyCompanionDiscovery | None = None
        self._panel_validator: LocalLlmPanelValidator | None = None
        self._line_segmenter = LineSegmenter(
            segmentation_mode=self._segmentation_mode,
            target_line_height_px=self._target_line_height_px,
            extra_left_pad_px=self._segmentation_extra_left_pad_px,
        )
        self._line_transcriber = LineTranscriber(preprocess_views=self._build_preprocess_views())
        self._line_first_parser = LineFirstParser()
        self._lexicon: LexiconArtifact | None = None
        self._reranker: LexiconReranker | None = None
        self._frame_benchmarks: list[dict[str, object]] = []

    def _build_preprocess_views(self) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
        # Align GUI validation labeling with sweep_preprocessing_headless gray_x3_lanczos.
        if self._preprocess_profile in {"sweep_gray_x3_lanczos", "gray_x3_lanczos", "sweep"}:
            return {
                "default": lambda image: preprocess_roi(
                    image,
                    scale_factor=3,
                    scale_algo="lanczos",
                    contrast_mode="none",
                )
            }

        return {
            "default": lambda image: preprocess_roi(
                image,
                scale_factor=self._scale_factor,
                scale_algo=self._scale_algo,
                contrast_mode=self._contrast_mode,
            ),
            "high_contrast": lambda image: preprocess_roi(
                image,
                scale_factor=self._scale_factor,
                scale_algo=self._scale_algo,
                contrast_mode="adaptive_threshold",
            ),
            "clahe": lambda image: preprocess_roi(
                image,
                scale_factor=self._scale_factor,
                scale_algo=self._scale_algo,
                contrast_mode="clahe",
            ),
        }

    @staticmethod
    def _read_int_parameter(parameters: dict[str, object], key: str, *, default: int) -> int:
        raw = parameters.get(key, default)
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, (int, float, str, bytes, bytearray)):
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default
        return default

    @staticmethod
    def _read_float_parameter(parameters: dict[str, object], key: str, *, default: float) -> float:
        raw = parameters.get(key, default)
        if isinstance(raw, bool):
            return float(raw)
        if isinstance(raw, (int, float, str, bytes, bytearray)):
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default
        return default

    @staticmethod
    def _read_bool_parameter(parameters: dict[str, object], key: str, *, default: bool) -> bool:
        raw = parameters.get(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, (str, bytes, bytearray)):
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)

    def _resolve_max_frames(self, request: PipelineRequest) -> int | None:
        raw_limit = request.parameters.get("max_frames")
        if raw_limit is None:
            raw_limit = self.config.parameters.get("max_frames")
        env_limit = os.getenv("ECHO_OCR_MAX_FRAMES", "").strip()
        if env_limit:
            raw_limit = env_limit
        if raw_limit is None:
            return None
        try:
            parsed = int(raw_limit)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _build_ocr_engine_with_fallback(self, preferred_engine: str) -> OcrEngine:
        if self._strict_ocr_engine_selection:
            return build_engine(preferred_engine)
        chain: list[str] = [preferred_engine]
        fb = self._fallback_engine_name
        if fb and fb != preferred_engine:
            chain.append(fb)
        for extra in ("easyocr", "paddleocr", "tesseract"):
            if extra not in chain:
                chain.append(extra)
        for name in chain:
            try:
                return build_engine(name)
            except Exception:
                continue
        return NoopOcrEngine()

    def _load_or_build_lexicon(self) -> LexiconArtifact | None:
        labels_candidates = [
            Path("labels/labels.json"),
            Path("labels/exact_lines.json"),
        ]
        lexicon_path = self._lexicon_path
        try:
            labels_path = next((path for path in labels_candidates if path.exists()), None)
            if labels_path is None:
                if lexicon_path.exists():
                    return LexiconArtifact.load(lexicon_path)
                return None

            rebuild_required = True
            if lexicon_path.exists():
                try:
                    rebuild_required = labels_path.stat().st_mtime > lexicon_path.stat().st_mtime
                except OSError:
                    rebuild_required = True
                if not rebuild_required:
                    return LexiconArtifact.load(lexicon_path)

            artifact = build_lexicon_artifact(labels_path)
            try:
                artifact.save(lexicon_path)
            except Exception:
                pass
            return artifact
        except Exception:
            return None
        return None

    def run(self, request: PipelineRequest) -> PipelineResult:
        try:
            self._frame_benchmarks = []
            self._ensure_components()
            series = load_dicom_series(request.dicom_path, load_pixels=False)
            output_dir = self._resolve_output_dir(request)
            max_frames = self._resolve_max_frames(request)
            companion_records = self._extract_study_companion_records(series, request.dicom_path)
            raw_line_predictions: list[dict[str, object]] = []
            records = companion_records or list(
                self._extract_records(
                    series,
                    request.dicom_path,
                    max_frames=max_frames,
                    raw_line_predictions=raw_line_predictions,
                )
            )
            if output_dir is not None and records:
                SidecarWriter(output_dir=output_dir, write_csv=True, write_jsonl=True).write(
                    request.dicom_path.stem,
                    records,
                )
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="ok",
                ai_result=self._to_ai_result(records, raw_line_predictions=raw_line_predictions),
                error=None,
            )
        except Exception as exc:
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="error",
                ai_result=None,
                error=str(exc),
            )

    def _ensure_components(self) -> None:
        if self._components_ready:
            return
        self.ocr_engine = (
            self._provided_ocr_engine
            if self._provided_ocr_engine is not None
            else RoutedOcrEngine(
                primary=self._build_ocr_engine_with_fallback(self._default_engine),
                fallback=(
                    self._build_ocr_engine_with_fallback(self._fallback_engine_name)
                    if self._fallback_engine_name and self._fallback_engine_name != self._default_engine
                    else None
                ),
            )
        )
        if isinstance(self.ocr_engine, RoutedOcrEngine):
            self._fallback_ocr_engine = self.ocr_engine.fallback
        self._lexicon = self._load_or_build_lexicon()
        self._reranker = LexiconReranker(self._lexicon) if self._lexicon is not None else None
        self._study_companion_discovery = (
            StudyCompanionDiscovery(
                recursive=self._study_companion_recursive,
                max_files=self._study_companion_max_files,
            )
            if self._study_companion_enabled
            else None
        )
        self._panel_validator = None
        if self._panel_validation_mode not in {"", "off", "disabled", "0", "false", "no"}:
            self._panel_validator = LocalLlmPanelValidator(
                config=PanelValidatorConfig(
                    model=self._panel_validation_model,
                    command=self._panel_validation_command,
                    timeout_s=self._panel_validation_timeout_s,
                    mode=self._panel_validation_mode,
                )
            )
        self._components_ready = True

    def ensure_components(self) -> None:
        self._ensure_components()

    def analyze_frame(
        self,
        frame: np.ndarray,
    ) -> tuple[OcrResult | None, PanelTranscription, list[AiMeasurement], tuple[int, int, int, int] | None]:
        self._ensure_components()
        _detection, _segmentation, ocr, panel, measurements, bbox = self._analyze_frame_detection(
            frame,
            self.box_detector.detect(frame),
        )
        return ocr, panel, measurements, bbox

    def analyze_frame_with_debug(
        self,
        frame: np.ndarray,
    ) -> tuple[
        RoiDetection,
        SegmentationResult,
        OcrResult | None,
        PanelTranscription,
        list[AiMeasurement],
        tuple[int, int, int, int] | None,
    ]:
        self._ensure_components()
        return self._analyze_frame_detection(frame, self.box_detector.detect(frame))

    def save_segmentation_debug_image(
        self,
        roi: np.ndarray,
        segmentation: SegmentationResult,
        output_path: Path,
    ) -> Path:
        return self._line_segmenter.save_debug_image(roi, segmentation, output_path)

    def _extract_study_companion_records(
        self,
        series: DicomSeries,
        path: Path,
    ) -> list[MeasurementRecord]:
        if self._study_companion_discovery is None:
            return []
        result = self._study_companion_discovery.discover(path, study_instance_uid=series.metadata.study_instance_uid)
        if not result.has_measurements:
            return []

        md = series.metadata
        study_uid = md.study_instance_uid or "unknown-study"
        series_uid = md.series_instance_uid or "unknown-series"
        default_sop_uid = md.sop_instance_uid or "unknown-sop"
        source_note = f"inspected_files={result.inspected_files};matched_files={result.matched_files}"
        records: list[MeasurementRecord] = []

        for order_idx, measurement in enumerate(result.measurements):
            source_info = _ParseSourceInfo(
                parser_source=measurement.source_kind,
                source_kind=measurement.source_kind,
                source_path=measurement.source_path,
                source_modality=measurement.source_modality or "",
                source_note=source_note,
            )
            records.append(
                MeasurementRecord(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    sop_instance_uid=measurement.source_sop_instance_uid or default_sop_uid,
                    frame_index=0,
                    measurement_name=measurement.name,
                    measurement_value=measurement.value,
                    measurement_unit=measurement.unit or "",
                    exact_line_text=measurement.exact_line_text or self._measurement_to_exact_line(
                        AiMeasurement(measurement.name, measurement.value, measurement.unit)
                    ),
                    line_confidence=measurement.confidence,
                    line_uncertain=False,
                    ocr_text_raw=measurement.exact_line_text,
                    ocr_confidence=measurement.confidence,
                    parser_confidence=measurement.confidence,
                    roi_bbox=(0, 0, 0, 0),
                    line_bbox=None,
                    text_order=measurement.order_hint if measurement.order_hint is not None else order_idx,
                    processed_at=MeasurementRecord.now_iso(),
                    pipeline_version=self.version,
                    ocr_engine="study-companion",
                    parser_source=source_info.parser_source,
                    source_kind=source_info.source_kind,
                    source_path=source_info.source_path,
                    source_modality=source_info.source_modality,
                    source_note=source_info.source_note,
                )
            )
        return records

    def _append_frame_processing_benchmark(
        self,
        *,
        frame_index: int,
        frame_latency_ms: float,
        ocr: OcrResult | None,
        panel: PanelTranscription,
        measurements: list[AiMeasurement],
        bbox: tuple[int, int, int, int] | None,
    ) -> None:
        effective_engine = (
            str(ocr.engine_name).strip()
            if ocr is not None and str(ocr.engine_name).strip()
            else str(self.ocr_engine.name).strip()
        )
        self._frame_benchmarks.append(
            {
                "frame_index": frame_index,
                "latency_ms": round(frame_latency_ms, 3),
                "ocr_engine": effective_engine,
                "line_count": len(panel.lines),
                "measurement_count": len(measurements),
                "ocr_confidence": float(ocr.confidence) if ocr is not None else 0.0,
                "uncertain_line_count": panel.uncertain_line_count,
                "fallback_invocations": panel.fallback_invocations,
                "engine_disagreement_count": panel.engine_disagreement_count,
                "used_detection": bool(bbox is not None),
            }
        )

    def _extract_records(
        self,
        series: DicomSeries,
        path: Path,
        *,
        max_frames: int | None = None,
        raw_line_predictions: list[dict[str, object]] | None = None,
    ) -> Iterable[MeasurementRecord]:
        md = series.metadata
        study_uid = md.study_instance_uid or "unknown-study"
        series_uid = md.series_instance_uid or "unknown-series"
        sop_uid = md.sop_instance_uid or "unknown-sop"
        frame_count = series.frame_count
        if max_frames is not None:
            frame_count = min(frame_count, max_frames)
        for frame_index in range(frame_count):
            frame = series.get_frame(frame_index)
            frame_started_at = time.perf_counter()
            ocr, panel, measurements, bbox = self._extract_measurements_for_frame(
                frame, self.box_detector.detect(frame)
            )
            frame_latency_ms = (time.perf_counter() - frame_started_at) * 1000.0
            self._append_frame_processing_benchmark(
                frame_index=frame_index,
                frame_latency_ms=frame_latency_ms,
                ocr=ocr,
                panel=panel,
                measurements=measurements,
                bbox=bbox,
            )
            if bbox is not None and panel.lines and raw_line_predictions is not None:
                for line in panel.lines:
                    raw_line_predictions.append(
                        {
                            "frame_index": frame_index,
                            "order": line.order,
                            "text": line.text,
                            "confidence": line.confidence,
                            "uncertain": line.uncertain,
                            "line_bbox": [bbox[0] + line.bbox[0], bbox[1] + line.bbox[1], line.bbox[2], line.bbox[3]],
                            "roi_bbox": list(bbox),
                            "ocr_engine": line.engine_name,
                            "parser_source": line.source,
                            "source_kind": "pixel_ocr",
                            "source_path": str(path),
                            "source_modality": getattr(md, "modality", None) or "",
                        }
                    )
            if ocr is None or bbox is None or not measurements:
                continue
            line_by_order = {line.order: line for line in panel.lines}
            for order_idx, measurement in enumerate(measurements):
                effective_order = measurement.order_hint if measurement.order_hint is not None else order_idx
                line_prediction = line_by_order.get(effective_order)
                absolute_line_bbox = None
                if line_prediction is not None:
                    lx, ly, lw, lh = line_prediction.bbox
                    absolute_line_bbox = (bbox[0] + lx, bbox[1] + ly, lw, lh)
                yield MeasurementRecord(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    sop_instance_uid=sop_uid,
                    frame_index=frame_index,
                    measurement_name=measurement.name,
                    measurement_value=measurement.value,
                    measurement_unit=measurement.unit or "",
                    exact_line_text=line_prediction.text if line_prediction is not None else self._measurement_to_exact_line(measurement),
                    line_confidence=line_prediction.confidence if line_prediction is not None else ocr.confidence,
                    line_uncertain=line_prediction.uncertain if line_prediction is not None else False,
                    ocr_text_raw=ocr.text,
                    ocr_confidence=ocr.confidence,
                    parser_confidence=ocr.confidence,
                    roi_bbox=bbox,
                    line_bbox=absolute_line_bbox,
                    text_order=effective_order,
                    processed_at=MeasurementRecord.now_iso(),
                    pipeline_version=self.version,
                    ocr_engine=ocr.engine_name,
                    parser_source=self._extract_parser_source(measurement.source) or "line_first",
                    source_kind="pixel_ocr",
                    source_path=str(path),
                    source_modality=getattr(md, "modality", None) or "",
                )

    def _extract_measurements_for_frame(
        self,
        frame: np.ndarray,
        detection: RoiDetection,
    ) -> tuple[OcrResult | None, PanelTranscription, list[AiMeasurement], tuple[int, int, int, int] | None]:
        _detection, _segmentation, ocr, panel, measurements, bbox = self._analyze_frame_detection(
            frame,
            detection,
        )
        return ocr, panel, measurements, bbox

    def _analyze_frame_detection(
        self,
        frame: np.ndarray,
        detection: RoiDetection,
    ) -> tuple[
        RoiDetection,
        SegmentationResult,
        OcrResult | None,
        PanelTranscription,
        list[AiMeasurement],
        tuple[int, int, int, int] | None,
    ]:
        if not detection.present or detection.bbox is None:
            return detection, SegmentationResult(header_trim_px=0, content_bbox=None, lines=()), None, PanelTranscription(), [], None
        x, y, bw, bh = detection.bbox
        roi = frame[y : y + bh, x : x + bw]
        primary_engine = self.ocr_engine.primary if isinstance(self.ocr_engine, RoutedOcrEngine) else self.ocr_engine
        scout_result = primary_engine.extract(roi)
        if self._fallback_ocr_engine is not None and not _scout_tokens_useful(scout_result):
            alt = self._fallback_ocr_engine.extract(roi)
            if _scout_tokens_useful(alt):
                scout_result = alt
        segmentation = self._line_segmenter.segment(roi, tokens=scout_result.tokens)
        panel = self._line_transcriber.transcribe(
            roi,
            segmentation,
            primary_engine=primary_engine,
            fallback_engine=self._fallback_ocr_engine,
        )
        if self._reranker is not None:
            panel = self._reranker.rerank_panel(panel)
        ocr = OcrResult(
            text=panel.combined_text,
            confidence=self._panel_confidence(panel),
            tokens=self._panel_tokens(panel),
            engine_name=self.ocr_engine.name,
        )
        measurements = self._parse_transcribed_panel(panel, confidence=ocr.confidence)
        measurements = self._maybe_apply_panel_validator(panel, measurements, confidence=ocr.confidence)
        measurements = apply_safe_measurement_corrections(measurements)
        if not measurements:
            if not panel.lines or ocr is None:
                return detection, segmentation, None, panel, [], None
            self._maybe_write_segmentation_debug(roi, detection, segmentation, panel)
            return detection, segmentation, ocr, panel, [], detection.bbox
        self._maybe_write_segmentation_debug(roi, detection, segmentation, panel)
        return detection, segmentation, ocr, panel, measurements, detection.bbox

    def _to_ai_result(
        self,
        records: list[MeasurementRecord],
        *,
        raw_line_predictions: list[dict[str, object]] | None = None,
    ) -> AiResult:
        seen: dict[tuple[str, str, str], tuple[AiMeasurement, MeasurementRecord]] = {}
        for record in records:
            decoded_line = parse_measurement_line(record.exact_line_text)
            raw_value = decoded_line.value or record.measurement_value
            raw_unit = (record.measurement_unit or decoded_line.unit or "").strip() or None
            normalized_item = apply_safe_measurement_corrections(
                [
                    AiMeasurement(
                        name=record.measurement_name,
                        value=raw_value,
                        unit=raw_unit,
                        source=f"exact_line:{record.exact_line_text}:{record.line_confidence:.3f}",
                        order_hint=record.text_order,
                        raw_ocr_text=record.exact_line_text,
                        corrected_value=record.measurement_value,
                    )
                ]
            )[0]
            key = (
                record.measurement_name.lower().strip(),
                normalized_item.value.strip(),
                (normalized_item.unit or "").strip().lower(),
            )
            if key not in seen or record.parser_confidence > seen[key][1].parser_confidence:
                seen[key] = (normalized_item, record)
        ordered = sorted(
            seen.values(),
            key=lambda item: (
                item[1].frame_index,
                item[1].text_order,
                item[1].roi_bbox[1],
                item[1].roi_bbox[0],
            ),
        )
        line_predictions_payload = [
            entry
            for entry in (raw_line_predictions or [])
            if isinstance(entry, dict) and str(entry.get("text", "")).strip()
        ]
        if not line_predictions_payload:
            line_predictions_payload = [
                {
                    "frame_index": record.frame_index,
                    "order": record.text_order,
                    "text": record.exact_line_text,
                    "confidence": record.line_confidence,
                    "uncertain": record.line_uncertain,
                    "line_bbox": list(record.line_bbox) if record.line_bbox is not None else None,
                    "roi_bbox": list(record.roi_bbox),
                    "ocr_engine": record.ocr_engine,
                    "parser_source": record.parser_source,
                    "source_kind": record.source_kind,
                    "source_path": record.source_path,
                    "source_modality": record.source_modality,
                }
                for _, record in ordered
            ]
        exact_lines_payload = [str(entry.get("text", "")).strip() for entry in line_predictions_payload]
        exact_lines_payload = [line for line in exact_lines_payload if line]
        source_kinds = sorted(
            {
                str(entry.get("source_kind", "")).strip() or "pixel_ocr"
                for entry in line_predictions_payload
            }
        ) or sorted({record.source_kind or "pixel_ocr" for _, record in ordered})
        parser_sources = sorted(
            {
                str(entry.get("parser_source", "")).strip()
                for entry in line_predictions_payload
                if str(entry.get("parser_source", "")).strip()
            }
        ) or sorted({record.parser_source for _, record in ordered if record.parser_source})
        model_suffix = self.ocr_engine.name if source_kinds == ["pixel_ocr"] else "+".join(source_kinds)
        engine_usage: dict[str, int] = {}
        latency_values: list[float] = []
        for frame_benchmark in self._frame_benchmarks:
            engine_name = str(frame_benchmark.get("ocr_engine", "")).strip() or "unknown"
            engine_usage[engine_name] = engine_usage.get(engine_name, 0) + 1
            latency_raw = frame_benchmark.get("latency_ms", 0.0)
            if isinstance(latency_raw, (int, float, str, bytes, bytearray)):
                try:
                    latency_values.append(float(latency_raw))
                except (TypeError, ValueError):
                    pass
        total_latency_ms = float(sum(latency_values)) if latency_values else 0.0
        mean_latency_ms = (total_latency_ms / len(latency_values)) if latency_values else 0.0
        if latency_values:
            latency_array = np.asarray(latency_values, dtype=np.float64)
            p95_latency_ms = float(np.percentile(latency_array, 95).item())
        else:
            p95_latency_ms = 0.0
        roi_boxes: list[OverlayBox] = []
        seen_rois: set[tuple[float, float, float, float]] = set()
        for entry in line_predictions_payload:
            source_kind_entry = str(entry.get("source_kind", "pixel_ocr")).strip() or "pixel_ocr"
            if source_kind_entry != "pixel_ocr":
                continue
            roi_bbox = entry.get("roi_bbox")
            if not isinstance(roi_bbox, list) or len(roi_bbox) != 4:
                continue
            try:
                roi_key = tuple(float(value) for value in roi_bbox)
            except (TypeError, ValueError):
                continue
            if roi_key[2] <= 0 or roi_key[3] <= 0:
                continue
            if roi_key in seen_rois:
                continue
            seen_rois.add(roi_key)
            confidence_raw = entry.get("confidence")
            confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else None
            roi_boxes.append(
                OverlayBox(
                    x=roi_key[0],
                    y=roi_key[1],
                    width=roi_key[2],
                    height=roi_key[3],
                    label="measurement_roi",
                    confidence=confidence,
                    color=f"#{MEASUREMENT_BOX_RGB[0]:02X}{MEASUREMENT_BOX_RGB[1]:02X}{MEASUREMENT_BOX_RGB[2]:02X}",
                )
            )
        if not roi_boxes:
            roi_boxes = [
                OverlayBox(
                    x=float(r.roi_bbox[0]),
                    y=float(r.roi_bbox[1]),
                    width=float(r.roi_bbox[2]),
                    height=float(r.roi_bbox[3]),
                    label="measurement_roi",
                    confidence=r.parser_confidence,
                    color=f"#{MEASUREMENT_BOX_RGB[0]:02X}{MEASUREMENT_BOX_RGB[1]:02X}{MEASUREMENT_BOX_RGB[2]:02X}",
                )
                for _, r in ordered
                if r.roi_bbox[2] > 0 and r.roi_bbox[3] > 0 and r.source_kind == "pixel_ocr"
            ]

        return AiResult(
            model_name=f"{self.name}:{model_suffix}",
            created_at=datetime.now(timezone.utc),
            boxes=roi_boxes,
            measurements=[m for m, _ in ordered],
            raw={
                "record_count": len(records),
                "pipeline_version": self.version,
                "segmentation_mode": self._segmentation_mode,
                "target_line_height_px": self._target_line_height_px,
                "source_kinds": source_kinds,
                "parser_sources": parser_sources,
                "exact_lines": exact_lines_payload,
                "line_predictions": line_predictions_payload,
                "uncertain_line_count": sum(
                    1 for entry in line_predictions_payload if bool(entry.get("uncertain"))
                ),
                "study_companion_used": any(record.source_kind != "pixel_ocr" for _, record in ordered),
                "ocr_engine_config": {
                    "requested": self._requested_engine,
                    "selected": self._default_engine,
                    "active": self.ocr_engine.name,
                    "fallback": self._fallback_ocr_engine.name if self._fallback_ocr_engine is not None else "",
                },
                "ocr_benchmark": {
                    "frame_count": len(self._frame_benchmarks),
                    "engine_usage": engine_usage,
                    "total_latency_ms": round(total_latency_ms, 3),
                    "mean_latency_ms": round(mean_latency_ms, 3),
                    "p95_latency_ms": round(p95_latency_ms, 3),
                    "frames": list(self._frame_benchmarks),
                },
                "startup_warning": self._startup_warning,
            },
        )

    @staticmethod
    def _extract_matching_ocr_line(raw_text: str, name: str, value: str) -> str:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        lowered_name = name.lower().strip()
        lowered_value = value.lower().strip()
        for line in lines:
            lowered = line.lower()
            if lowered_name in lowered and lowered_value in lowered:
                return line
        for line in lines:
            if lowered_value in line.lower():
                return line
        return lines[0] if lines else raw_text.strip()

    @staticmethod
    def _measurement_to_exact_line(measurement: AiMeasurement) -> str:
        parts = [measurement.name, measurement.value, measurement.unit or ""]
        return canonicalize_exact_line(" ".join(part for part in parts if part))

    @staticmethod
    def _panel_confidence(panel: PanelTranscription) -> float:
        if not panel.lines:
            return 0.0
        return float(sum(line.confidence for line in panel.lines) / len(panel.lines))

    @staticmethod
    def _panel_tokens(panel: PanelTranscription) -> list[OcrToken]:
        tokens: list[OcrToken] = []
        for line in panel.lines:
            for candidate in line.candidates:
                if candidate.source == line.source and candidate.engine_name == line.engine_name:
                    tokens.extend(candidate.tokens)
                    break
        return tokens

    def _parse_transcribed_panel(self, panel: PanelTranscription, *, confidence: float) -> list[AiMeasurement]:
        lines: list[str] = []
        line_orders: list[int] = []
        for line in panel.lines:
            text = line.text.strip()
            if not text:
                continue
            lines.append(line.text)
            line_orders.append(line.order)
        measurements = self._line_first_parser.parse_lines(lines, confidence=confidence)
        remapped_measurements: list[AiMeasurement] = []
        for measurement in measurements:
            order_hint = measurement.order_hint
            if order_hint is not None and 0 <= int(order_hint) < len(line_orders):
                remapped_measurements.append(
                    AiMeasurement(
                        name=measurement.name,
                        value=measurement.value,
                        unit=measurement.unit,
                        source=measurement.source,
                        order_hint=line_orders[int(order_hint)],
                        raw_ocr_text=measurement.raw_ocr_text,
                        corrected_value=measurement.corrected_value,
                        flags=list(measurement.flags or []),
                    )
                )
            else:
                remapped_measurements.append(measurement)
        return self._attach_line_sources(remapped_measurements, panel, parser_source="line_first")

    def _maybe_apply_panel_validator(
        self,
        panel: PanelTranscription,
        measurements: list[AiMeasurement],
        *,
        confidence: float,
    ) -> list[AiMeasurement]:
        if self._panel_validator is None:
            return measurements
        result = self._panel_validator.validate(panel, measurements, confidence=confidence)
        if not result.applied or not result.measurements:
            return measurements
        return self._attach_line_sources(
            list(result.measurements),
            panel,
            parser_source=f"panel_validator:{self._panel_validation_model}",
        )

    @staticmethod
    def _build_exact_line_source(line_text: str, *, confidence: float, parser_source: str) -> str:
        source = f"exact_line:{canonicalize_exact_line(line_text)}:{confidence:.3f}"
        parser_tag = parser_source.strip().replace("|", "/")
        if parser_tag:
            source += f"|parser={parser_tag}"
        return source

    @staticmethod
    def _extract_parser_source(source: str | None) -> str:
        if not source:
            return ""
        marker = "|parser="
        if marker in source:
            return source.split(marker, maxsplit=1)[1].split("|", maxsplit=1)[0].strip()
        return ""

    def _attach_line_sources(
        self,
        measurements: list[AiMeasurement],
        panel: PanelTranscription,
        *,
        parser_source: str,
    ) -> list[AiMeasurement]:
        line_by_order = {line.order: line for line in panel.lines}
        attached: list[AiMeasurement] = []
        for fallback_index, measurement in enumerate(measurements):
            line = line_by_order.get(measurement.order_hint if measurement.order_hint is not None else fallback_index)
            if line is None:
                source = self._build_exact_line_source(
                    self._measurement_to_exact_line(measurement),
                    confidence=0.0,
                    parser_source=parser_source,
                )
                if measurement.source == source and measurement.order_hint is not None:
                    attached.append(measurement)
                else:
                    attached.append(
                        AiMeasurement(
                            name=measurement.name,
                            value=measurement.value,
                            unit=measurement.unit,
                            source=source,
                            order_hint=measurement.order_hint,
                            raw_ocr_text=measurement.raw_ocr_text,
                            corrected_value=measurement.corrected_value,
                            flags=list(measurement.flags or []),
                        )
                    )
                continue
            attached.append(
                AiMeasurement(
                    name=measurement.name,
                    value=measurement.value,
                    unit=measurement.unit,
                    source=self._build_exact_line_source(
                        line.text,
                        confidence=line.confidence,
                        parser_source=parser_source,
                    ),
                    order_hint=line.order,
                    raw_ocr_text=measurement.raw_ocr_text or line.text,
                    corrected_value=measurement.corrected_value,
                    flags=list(measurement.flags or []),
                )
            )
        return attached

    def _maybe_write_segmentation_debug(
        self,
        roi: np.ndarray,
        detection: RoiDetection,
        segmentation: SegmentationResult,
        panel: PanelTranscription,
    ) -> None:
        if not self._save_segmentation_debug or not self._segmentation_debug_dir or not panel.lines:
            return
        try:
            debug_dir = Path(self._segmentation_debug_dir)
            x, y, bw, bh = detection.bbox or (0, 0, 0, 0)
            file_name = f"bbox_{x}_{y}_{bw}_{bh}_lines_{len(panel.lines)}.png"
            self._line_segmenter.save_debug_image(roi, segmentation, debug_dir / file_name)
        except Exception:
            return
