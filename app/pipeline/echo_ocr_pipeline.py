from __future__ import annotations

import importlib
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import AiMeasurement, AiResult, DicomSeries, OverlayBox, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import BasePipeline, PipelineConfig
from app.pipeline.echo_ocr_box_detector import (
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
)
from app.pipeline.line_first_parser import LineFirstParser
from app.pipeline.line_segmenter import DEFAULT_HEADER_TRIM_PX, LineSegmenter, SegmentationResult
from app.pipeline.line_transcriber import LineTranscriber, PanelTranscription
from app.pipeline.lexicon_builder import LexiconArtifact, build_lexicon_artifact
from app.pipeline.lexicon_reranker import LexiconReranker
from app.pipeline.measurement_decoder import canonicalize_exact_line
from app.pipeline.echo_ocr_schema import MeasurementRecord
from app.pipeline.echo_sidecar_writer import SidecarWriter
from app.pipeline.measurement_parsers import MeasurementParser, RegexMeasurementParser, build_parser
from app.pipeline.ocr_engines import OcrEngine, OcrResult, OcrToken, build_engine


DEFAULT_LEXICON_PATH = Path("docs/ocr_redesign/exact_lines_lexicon.json")
MEASUREMENT_BOX_RGB = (0x1A, 0x21, 0x29)


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3 and image.shape[-1] >= 3:
        rgb = image[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {image.shape}")


class MeasurementBoxDetector(Protocol):
    def detect(self, frame: np.ndarray) -> RoiDetection: ...


def preprocess_roi(
    roi: np.ndarray,
    scale_factor: int | None = 3,
    scale_algo: str | None = "lanczos",
    contrast_mode: str | None = "none",
) -> np.ndarray:
    if scale_factor is None:
        try:
            scale_factor = int(os.getenv("ECHO_OCR_UPSCALE_FACTOR", "2"))
        except:
            scale_factor = 2
    if scale_algo is None:
        scale_algo = os.getenv("ECHO_OCR_UPSCALE_INTERPOLATION", "cubic").lower()
    if contrast_mode is None:
        contrast_mode = os.getenv("ECHO_OCR_CONTRAST_MODE", "clahe").lower()

    gray = _to_gray(roi)
    if gray.size == 0:
        return gray

    try:
        cv2: Any = importlib.import_module("cv2")

        # 1. Contrast Adjustment
        if contrast_mode == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        elif contrast_mode == "adaptive_threshold":
            # Just mild equalization before the blur
            enhanced = cv2.equalizeHist(gray)
        else:  # "none" or default
            enhanced = gray

        # 2. Unsharp masking to sharpen text edges
        gaussian = cv2.GaussianBlur(enhanced, (5, 5), 1.0)
        unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

        # 3. Upscale BEFORE thresholding to prevent jagged edges on small text
        scale = max(1, min(scale_factor, 6))
        if scale > 1:
            interpolation_map = {
                "linear": cv2.INTER_LINEAR,
                "cubic": cv2.INTER_CUBIC,
                "lanczos": cv2.INTER_LANCZOS4,
            }
            inter_flag = interpolation_map.get(scale_algo, cv2.INTER_CUBIC)

            w = int(unsharp.shape[1] * scale)
            h = int(unsharp.shape[0] * scale)
            unsharp = cv2.resize(unsharp, (w, h), interpolation=inter_flag)

        if contrast_mode == "adaptive_threshold":
            # 4. Adaptive thresholding instead of Otsu's
            thresh = cv2.adaptiveThreshold(
                unsharp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            # 4. Otsu's thresholding for pure B&W text
            _, thresh = cv2.threshold(unsharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 5. Mild morphological closing to bridge gaps in thin fonts
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        clean = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return clean

    except ImportError:
        # Fallback to pure numpy stretching and basic nearest upscale
        p5 = np.percentile(gray, 5)
        p95 = np.percentile(gray, 95)
        if p95 <= p5:
            stretched = gray
        else:
            stretched = (((gray.astype(np.float32) - p5) * (255.0 / (p95 - p5))).clip(0, 255).astype(np.uint8))

        scale = max(1, min(scale_factor, 6))
        if scale <= 1:
            return stretched
        return np.repeat(np.repeat(stretched, scale, axis=0), scale, axis=1)


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


class EchoOcrPipeline(BasePipeline):
    name = "echo-ocr"
    version = "v2-line-first"

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None = None,
        box_detector: MeasurementBoxDetector | None = None,
        parser: MeasurementParser | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        parameters = dict(self.config.parameters)
        self._provided_ocr_engine = ocr_engine
        self._provided_parser = parser
        self._default_engine = (
            str(parameters.get("ocr_engine", os.getenv("ECHO_OCR_ENGINE", "easyocr")))
            .strip()
            .lower()
        )
        self._parser_mode = (
            str(parameters.get("parser_mode", os.getenv("ECHO_PARSER_MODE", "regex")))
            .strip()
            .lower()
        )
        self._parser_parameters = dict(parameters)
        self._scale_factor = self._read_int_parameter(parameters, "scale_factor", default=3)
        self._scale_algo = str(parameters.get("scale_algo", "lanczos")).strip().lower()
        self._contrast_mode = str(parameters.get("contrast_mode", "none")).strip().lower()
        self._fallback_engine_name = str(
            parameters.get("fallback_ocr_engine", os.getenv("ECHO_OCR_FALLBACK_ENGINE", ""))
        ).strip().lower()
        self._lexicon_path = Path(str(parameters.get("lexicon_path", DEFAULT_LEXICON_PATH))).expanduser()
        self._segmentation_debug_dir = str(parameters.get("segmentation_debug_dir", "")).strip()
        self._save_segmentation_debug = (
            str(parameters.get("save_segmentation_debug", "0")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.ocr_engine: OcrEngine = NoopOcrEngine()
        self.parser: MeasurementParser = RegexMeasurementParser()
        self._components_ready = False
        self.box_detector = box_detector or TopLeftBlueGrayBoxDetector()
        self._fallback_ocr_engine: OcrEngine | None = None
        self._line_segmenter = LineSegmenter(default_header_trim_px=DEFAULT_HEADER_TRIM_PX)
        self._line_transcriber = LineTranscriber(
            preprocess_views={
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
            }
        )
        self._line_first_parser = LineFirstParser(fallback_parser=RegexMeasurementParser())
        self._lexicon: LexiconArtifact | None = None
        self._reranker: LexiconReranker | None = None

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

    @staticmethod
    def _build_ocr_engine_with_fallback(preferred_engine: str) -> OcrEngine:
        for name in (preferred_engine, "easyocr", "paddleocr", "tesseract"):
            try:
                return build_engine(name)
            except Exception:
                continue
        return NoopOcrEngine()

    def _load_or_build_lexicon(self) -> LexiconArtifact | None:
        labels_path = Path("labels/exact_lines.json")
        lexicon_path = self._lexicon_path
        try:
            if lexicon_path.exists():
                return LexiconArtifact.load(lexicon_path)
            if labels_path.exists():
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
            self._ensure_components()
            series = load_dicom_series(request.dicom_path, load_pixels=False)
            output_dir = self._resolve_output_dir(request)
            max_frames = self._resolve_max_frames(request)
            records = list(
                self._extract_records(series, request.dicom_path, max_frames=max_frames)
            )
            if output_dir is not None and records:
                SidecarWriter(output_dir=output_dir, write_csv=True, write_jsonl=True).write(
                    request.dicom_path.stem,
                    records,
                )
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="ok",
                ai_result=self._to_ai_result(records),
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
        if self._provided_parser is not None:
            self.parser = self._provided_parser
        else:
            try:
                self.parser = build_parser(self._parser_mode, parameters=self._parser_parameters)
            except Exception:
                self.parser = RegexMeasurementParser()
        self._lexicon = self._load_or_build_lexicon()
        self._reranker = LexiconReranker(self._lexicon) if self._lexicon is not None else None
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

    def _extract_records(
        self,
        series: DicomSeries,
        _path: Path,
        *,
        max_frames: int | None = None,
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
            ocr, panel, measurements, bbox = self._extract_measurements_for_frame(
                frame, self.box_detector.detect(frame)
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
        if not measurements:
            fallback = self.parser.parse(ocr.text, confidence=ocr.confidence)
            measurements = self._attach_line_sources(fallback, panel)
        if not measurements:
            return detection, segmentation, None, panel, [], None
        self._maybe_write_segmentation_debug(roi, detection, segmentation, panel)
        return detection, segmentation, ocr, panel, measurements, detection.bbox

    def _to_ai_result(self, records: list[MeasurementRecord]) -> AiResult:
        seen: dict[tuple[str, str, str], tuple[AiMeasurement, MeasurementRecord]] = {}
        for record in records:
            key = (
                record.measurement_name.lower().strip(),
                record.measurement_value.strip(),
                (record.measurement_unit or "").strip().lower(),
            )
            if key not in seen or record.parser_confidence > seen[key][1].parser_confidence:
                seen[key] = (
                    AiMeasurement(
                        name=record.measurement_name,
                        value=record.measurement_value,
                        unit=record.measurement_unit or None,
                        source=f"exact_line:{record.exact_line_text}:{record.line_confidence:.3f}",
                        order_hint=record.text_order,
                    ),
                    record,
                )
        ordered = sorted(
            seen.values(),
            key=lambda item: (
                item[1].frame_index,
                item[1].text_order,
                item[1].roi_bbox[1],
                item[1].roi_bbox[0],
            ),
        )

        return AiResult(
            model_name=f"{self.name}:{self.ocr_engine.name}",
            created_at=datetime.now(timezone.utc),
            boxes=[
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
            ],
            measurements=[m for m, _ in ordered],
            raw={
                "record_count": len(records),
                "pipeline_version": self.version,
                "exact_lines": [record.exact_line_text for _, record in ordered],
                "line_predictions": [
                    {
                        "order": record.text_order,
                        "text": record.exact_line_text,
                        "confidence": record.line_confidence,
                        "uncertain": record.line_uncertain,
                        "line_bbox": list(record.line_bbox) if record.line_bbox is not None else None,
                    }
                    for _, record in ordered
                ],
                "uncertain_line_count": sum(1 for _, record in ordered if record.line_uncertain),
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
        lines = [line.text for line in panel.lines if line.text.strip()]
        measurements = self._line_first_parser.parse_lines(lines, confidence=confidence)
        return self._attach_line_sources(measurements, panel)

    @staticmethod
    def _attach_line_sources(measurements: list[AiMeasurement], panel: PanelTranscription) -> list[AiMeasurement]:
        line_by_order = {line.order: line for line in panel.lines}
        attached: list[AiMeasurement] = []
        for fallback_index, measurement in enumerate(measurements):
            line = line_by_order.get(measurement.order_hint if measurement.order_hint is not None else fallback_index)
            if line is None:
                source = measurement.source or (
                    f"exact_line:{measurement.name} {measurement.value}:{measurement.order_hint or fallback_index}"
                )
                if measurement.source == source:
                    attached.append(measurement)
                else:
                    attached.append(
                        AiMeasurement(
                            name=measurement.name,
                            value=measurement.value,
                            unit=measurement.unit,
                            source=source,
                            order_hint=measurement.order_hint,
                        )
                    )
                continue
            attached.append(
                AiMeasurement(
                    name=measurement.name,
                    value=measurement.value,
                    unit=measurement.unit,
                    source=f"exact_line:{line.text}:{line.confidence:.3f}",
                    order_hint=line.order,
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
