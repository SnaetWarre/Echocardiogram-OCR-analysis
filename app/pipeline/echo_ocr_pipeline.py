from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import AiMeasurement, AiResult, OverlayBox, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import BasePipeline
from app.pipeline.echo_ocr_box_detector import (
    RoiDetection,
    TopLeftBlueGrayBoxDetector,
    _color_distance,  # re-export for tests
    _to_gray,
)
from app.pipeline.echo_ocr_schema import MeasurementRecord
from app.pipeline.echo_sidecar_writer import SidecarWriter
from app.pipeline.measurement_parsers import MeasurementParser, RegexMeasurementParser, build_parser
from app.pipeline.ocr_engines import OcrEngine, OcrResult, build_engine


class MeasurementBoxDetector(Protocol):
    def detect(self, frame: np.ndarray) -> RoiDetection:
        ...


def _upscale_factor() -> int:
    raw = str(os.getenv("ECHO_OCR_UPSCALE_FACTOR", "2")).strip()
    try:
        factor = int(raw)
    except Exception:
        factor = 2
    return max(1, min(factor, 6))


def _upscale_interpolation() -> str:
    method = str(os.getenv("ECHO_OCR_UPSCALE_INTERPOLATION", "nearest")).strip().lower()
    if method in {"nearest", "linear", "cubic", "lanczos"}:
        return method
    return "nearest"


def preprocess_roi(roi: np.ndarray) -> np.ndarray:
    gray = _to_gray(roi)
    if gray.size == 0:
        return gray
    p5 = np.percentile(gray, 5)
    p95 = np.percentile(gray, 95)
    if p95 <= p5:
        stretched = gray
    else:
        stretched = ((gray.astype(np.float32) - p5) * (255.0 / (p95 - p5))).clip(0, 255).astype(np.uint8)
    scale = _upscale_factor()
    if scale <= 1:
        return stretched
    interpolation = _upscale_interpolation()
    if interpolation == "nearest":
        return np.repeat(np.repeat(stretched, scale, axis=0), scale, axis=1)
    try:
        import cv2  # type: ignore

        interpolation_flag = {
            "linear": cv2.INTER_LINEAR,
            "cubic": cv2.INTER_CUBIC,
            "lanczos": cv2.INTER_LANCZOS4,
        }.get(interpolation, cv2.INTER_NEAREST)
        return cv2.resize(
            stretched,
            (stretched.shape[1] * scale, stretched.shape[0] * scale),
            interpolation=interpolation_flag,
        )
    except Exception:
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
        ocr_engine: Optional[OcrEngine] = None,
        box_detector: Optional[MeasurementBoxDetector] = None,
        parser: Optional[MeasurementParser] = None,
        config=None,
    ) -> None:
        super().__init__(config=config)
        parameters = dict(self.config.parameters)
        self._provided_ocr_engine = ocr_engine
        self._provided_parser = parser
        self._default_engine = str(parameters.get("ocr_engine", os.getenv("ECHO_OCR_ENGINE", "easyocr"))).strip().lower()
        self._parser_mode = str(parameters.get("parser_mode", os.getenv("ECHO_PARSER_MODE", "regex"))).strip().lower()
        self._parser_parameters = dict(parameters)
        self.ocr_engine: OcrEngine = NoopOcrEngine()
        self.parser: MeasurementParser = RegexMeasurementParser()
        self._components_ready = False
        self.box_detector = box_detector or TopLeftBlueGrayBoxDetector()

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
            records = list(self._extract_records(series, request.dicom_path))
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
        except Exception as exc:  # noqa: BLE001
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

    def _extract_records(self, series, _path: Path) -> Iterable[MeasurementRecord]:
        md = series.metadata
        study_uid = md.study_instance_uid or "unknown-study"
        series_uid = md.series_instance_uid or "unknown-series"
        sop_uid = md.sop_instance_uid or "unknown-sop"
        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            ocr, measurements, bbox = self._extract_measurements_for_frame(frame, self.box_detector.detect(frame))
            if ocr is None or bbox is None or not measurements:
                continue
            for measurement in measurements:
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
                    processed_at=MeasurementRecord.now_iso(),
                    pipeline_version=self.version,
                    ocr_engine=ocr.engine_name,
                )

    def _extract_measurements_for_frame(
        self,
        frame: np.ndarray,
        detection: RoiDetection,
    ) -> Tuple[Optional[OcrResult], List[AiMeasurement], Optional[Tuple[int, int, int, int]]]:
        if not detection.present or detection.bbox is None:
            return None, [], None
        x, y, bw, bh = detection.bbox
        roi = frame[y : y + bh, x : x + bw]
        prepared = preprocess_roi(roi)
        ocr = self.ocr_engine.extract(prepared)
        measurements = self.parser.parse(ocr.text, confidence=ocr.confidence)
        if not measurements:
            return None, [], None
        return ocr, measurements, detection.bbox

    def _to_ai_result(self, records: List[MeasurementRecord]) -> AiResult:
        seen: Dict[tuple, Tuple[AiMeasurement, MeasurementRecord]] = {}
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
                for _, r in seen.values()
            ],
            measurements=[m for m, _ in seen.values()],
            raw={"record_count": len(records), "pipeline_version": self.version},
        )
