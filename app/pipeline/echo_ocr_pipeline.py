from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import AiMeasurement, AiResult, OverlayBox, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import BasePipeline
from app.pipeline.echo_ocr_box_detector import (
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
    _to_gray,
)
from app.pipeline.echo_ocr_schema import MeasurementRecord
from app.pipeline.echo_sidecar_writer import SidecarWriter
from app.pipeline.measurement_parsers import MeasurementParser, RegexMeasurementParser, build_parser
from app.pipeline.ocr_engines import OcrEngine, OcrResult, build_engine


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
        import cv2  # type: ignore
        
        # 1. Contrast Adjustment
        if contrast_mode == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        elif contrast_mode == "adaptive_threshold":
            # Just mild equalization before the blur
            enhanced = cv2.equalizeHist(gray)
        else: # "none" or default
            enhanced = gray
            
        # 2. Unsharp masking to sharpen text edges
        gaussian = cv2.GaussianBlur(enhanced, (5, 5), 1.0)
        unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
        
        # 3. Upscale BEFORE thresholding to prevent jagged edges on small text
        scale = max(1, min(scale_factor, 6))
        if scale > 1:
            inter_flag = {
                "linear": cv2.INTER_LINEAR,
                "cubic": cv2.INTER_CUBIC,
                "lanczos": cv2.INTER_LANCZOS4,
            }.get(scale_algo, cv2.INTER_CUBIC)
            
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


class EchoOcrPipeline(BasePipeline):
    name = "echo-ocr"
    version = "v1"

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None = None,
        box_detector: MeasurementBoxDetector | None = None,
        parser: MeasurementParser | None = None,
        config=None,
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
        self.ocr_engine: OcrEngine = NoopOcrEngine()
        self.parser: MeasurementParser = RegexMeasurementParser()
        self._components_ready = False
        self.box_detector = box_detector or TopLeftBlueGrayBoxDetector()

    @staticmethod
    def _read_int_parameter(parameters: dict[str, object], key: str, *, default: int) -> int:
        raw = parameters.get(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
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
            else self._build_ocr_engine_with_fallback(self._default_engine)
        )
        if self._provided_parser is not None:
            self.parser = self._provided_parser
        else:
            try:
                self.parser = build_parser(self._parser_mode, parameters=self._parser_parameters)
            except Exception:
                self.parser = RegexMeasurementParser()
        self._components_ready = True

    def _extract_records(
        self,
        series,
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
            ocr, measurements, bbox = self._extract_measurements_for_frame(
                frame, self.box_detector.detect(frame)
            )
            if ocr is None or bbox is None or not measurements:
                continue
            for order_idx, measurement in enumerate(measurements):
                effective_order = measurement.order_hint if measurement.order_hint is not None else order_idx
                yield MeasurementRecord(
                    study_uid=study_uid,
                    series_uid=series_uid,
                    sop_instance_uid=sop_uid,
                    frame_index=frame_index,
                    measurement_name=measurement.name,
                    measurement_value=measurement.value,
                    measurement_unit=measurement.unit or "",
                    ocr_text_raw=ocr.text,
                    ocr_confidence=ocr.confidence,
                    parser_confidence=ocr.confidence,
                    roi_bbox=bbox,
                    text_order=effective_order,
                    processed_at=MeasurementRecord.now_iso(),
                    pipeline_version=self.version,
                    ocr_engine=ocr.engine_name,
                )

    def _extract_measurements_for_frame(
        self,
        frame: np.ndarray,
        detection: RoiDetection,
    ) -> tuple[OcrResult | None, list[AiMeasurement], tuple[int, int, int, int] | None]:
        if not detection.present or detection.bbox is None:
            return None, [], None
        x, y, bw, bh = detection.bbox
        roi = frame[y : y + bh, x : x + bw]
        prepared = preprocess_roi(
            roi,
            scale_factor=self._scale_factor,
            scale_algo=self._scale_algo,
            contrast_mode=self._contrast_mode,
        )
        ocr = self.ocr_engine.extract(prepared)
        measurements = self.parser.parse(ocr.text, confidence=ocr.confidence)
        if not measurements:
            return None, [], None
        return ocr, measurements, detection.bbox

    def _to_ai_result(self, records: list[MeasurementRecord]) -> AiResult:
        seen: dict[tuple, tuple[AiMeasurement, MeasurementRecord]] = {}
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
                        source="echo_ocr_pipeline",
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
                    label="measurement_box",
                    confidence=r.parser_confidence,
                )
                for _, r in ordered
            ],
            measurements=[m for m, _ in ordered],
            raw={"record_count": len(records), "pipeline_version": self.version},
        )
