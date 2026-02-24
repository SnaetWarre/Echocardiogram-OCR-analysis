from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

import numpy as np

from app.io.dicom_loader import load_dicom_series
from app.models.types import AiMeasurement, AiResult, OverlayBox, PipelineRequest, PipelineResult
from app.pipeline.ai_pipeline import BasePipeline
from app.pipeline.echo_ocr_schema import MeasurementRecord
from app.pipeline.measurement_parsers import MeasurementParser, RegexMeasurementParser, build_parser
from app.pipeline.echo_sidecar_writer import SidecarWriter
from app.pipeline.ocr_engines import OcrEngine, OcrResult, build_engine


@dataclass(frozen=True)
class RoiDetection:
    present: bool
    bbox: Optional[Tuple[int, int, int, int]]
    confidence: float


class MeasurementBoxDetector(Protocol):
    def detect(self, frame: np.ndarray) -> RoiDetection:
        ...


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame.astype(np.uint8, copy=False)
    if frame.ndim == 3 and frame.shape[-1] >= 3:
        rgb = frame[..., :3].astype(np.float32)
        gray = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    raise ValueError(f"Unsupported frame shape: {frame.shape}")


def preprocess_roi(roi: np.ndarray) -> np.ndarray:
    gray = _to_gray(roi)
    if gray.size == 0:
        return gray
    p5 = np.percentile(gray, 5)
    p95 = np.percentile(gray, 95)
    if p95 <= p5:
        return gray
    stretched = ((gray.astype(np.float32) - p5) * (255.0 / (p95 - p5))).clip(0, 255).astype(np.uint8)
    # Nearest-neighbor upscale improves OCR readability for tiny overlays.
    return np.repeat(np.repeat(stretched, 2, axis=0), 2, axis=1)


class TopLeftBlueGrayBoxDetector:
    def __init__(
        self,
        *,
        top_left_height_ratio: float = 0.45,
        top_left_width_ratio: float = 0.55,
        min_pixels: int = 240,
        min_presence_confidence: float = 0.04,
    ) -> None:
        self.top_left_height_ratio = top_left_height_ratio
        self.top_left_width_ratio = top_left_width_ratio
        self.min_pixels = min_pixels
        self.min_presence_confidence = min_presence_confidence

    def detect(self, frame: np.ndarray) -> RoiDetection:
        h, w = frame.shape[:2]
        roi_h = max(8, int(h * self.top_left_height_ratio))
        roi_w = max(8, int(w * self.top_left_width_ratio))
        search = frame[:roi_h, :roi_w]

        if search.ndim != 3 or search.shape[-1] < 3:
            gray = _to_gray(search)
            mask = gray > 180
        else:
            rgb = search[..., :3].astype(np.int16)
            r = rgb[..., 0]
            g = rgb[..., 1]
            b = rgb[..., 2]
            # Blue-gray label box: moderate brightness + blue channel not lower than red.
            mask = (b > 70) & (g > 65) & (r > 45) & (b >= r) & (np.abs(g - b) < 70)

        ys, xs = np.where(mask)
        if xs.size < self.min_pixels:
            return RoiDetection(present=False, bbox=None, confidence=0.0)

        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        width = max(x2 - x1 + 1, 1)
        height = max(y2 - y1 + 1, 1)
        area = width * height
        if area <= 0:
            return RoiDetection(present=False, bbox=None, confidence=0.0)
        fill_ratio = float(xs.size / area)
        confidence = float(min(1.0, fill_ratio))
        if confidence < self.min_presence_confidence:
            return RoiDetection(present=False, bbox=None, confidence=confidence)
        return RoiDetection(present=True, bbox=(x1, y1, width, height), confidence=confidence)


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
        default_engine = str(parameters.get("ocr_engine", os.getenv("ECHO_OCR_ENGINE", "tesseract")))
        parser_mode = str(parameters.get("parser_mode", os.getenv("ECHO_PARSER_MODE", "regex")))
        llm_model = str(parameters.get("llm_model", os.getenv("ECHO_LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")))
        llm_command = str(parameters.get("llm_command", os.getenv("ECHO_LLM_COMMAND", "ollama")))
        llm_timeout_s = float(parameters.get("llm_timeout_s", os.getenv("ECHO_LLM_TIMEOUT_S", "30.0")))
        parser_parameters = {
            **parameters,
            "llm_model": llm_model,
            "llm_command": llm_command,
            "llm_timeout_s": llm_timeout_s,
        }
        self._provided_ocr_engine = ocr_engine
        self._provided_parser = parser
        self._default_engine = default_engine
        self._parser_mode = parser_mode
        self._parser_parameters = parser_parameters

        self.ocr_engine: OcrEngine = NoopOcrEngine()
        self.parser: MeasurementParser = RegexMeasurementParser()
        self._components_ready = False
        self.box_detector = box_detector or TopLeftBlueGrayBoxDetector()

    @staticmethod
    def _build_ocr_engine_with_fallback(preferred_engine: str) -> OcrEngine:
        engine_order = [preferred_engine, "paddleocr", "tesseract", "easyocr"]
        seen = set()
        for name in engine_order:
            lowered = name.strip().lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            try:
                return build_engine(lowered)
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
                writer = SidecarWriter(output_dir=output_dir, write_csv=True, write_jsonl=True)
                writer.write(request.dicom_path.stem, records)
            ai_result = self._to_ai_result(records)
            return PipelineResult(
                dicom_path=request.dicom_path,
                status="ok",
                ai_result=ai_result,
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
        if self._provided_ocr_engine is not None:
            self.ocr_engine = self._provided_ocr_engine
        else:
            self.ocr_engine = self._build_ocr_engine_with_fallback(self._default_engine)

        if self._provided_parser is not None:
            self.parser = self._provided_parser
        else:
            try:
                self.parser = build_parser(self._parser_mode, parameters=self._parser_parameters)
            except Exception:
                self.parser = RegexMeasurementParser()
        self._components_ready = True

    def _extract_records(self, series, path: Path) -> Iterable[MeasurementRecord]:
        md = series.metadata
        study_uid = md.study_instance_uid or "unknown-study"
        series_uid = md.series_instance_uid or "unknown-series"
        sop_uid = md.sop_instance_uid or "unknown-sop"

        for frame_index in range(series.frame_count):
            frame = series.get_frame(frame_index)
            detection = self.box_detector.detect(frame)
            ocr, measurements, chosen_bbox, parse_conf = self._extract_measurements_for_frame(
                frame,
                detection,
            )
            if not measurements or ocr is None or chosen_bbox is None:
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
                    parser_confidence=parse_conf,
                    roi_bbox=chosen_bbox,
                    processed_at=MeasurementRecord.now_iso(),
                    pipeline_version=self.version,
                )

    def _extract_measurements_for_frame(
        self,
        frame: np.ndarray,
        detection: RoiDetection,
    ) -> Tuple[Optional[OcrResult], List[AiMeasurement], Optional[Tuple[int, int, int, int]], float]:
        # Try detector ROI first.
        candidates: List[Tuple[Tuple[int, int, int, int], float]] = []
        if detection.present and detection.bbox is not None:
            candidates.append((detection.bbox, max(0.2, detection.confidence)))

        # Fallback boxes tuned for top-left echocardiogram measurement overlays.
        h, w = frame.shape[:2]
        fallback_candidates = [
            (10, 5, int(w * 0.22), int(h * 0.10)),
            (10, 5, int(w * 0.26), int(h * 0.13)),
            (15, 10, int(w * 0.30), int(h * 0.16)),
            (0, 0, int(w * 0.35), int(h * 0.18)),
        ]
        for x, y, bw, bh in fallback_candidates:
            x = max(0, min(x, w - 2))
            y = max(0, min(y, h - 2))
            bw = max(20, min(bw, w - x))
            bh = max(20, min(bh, h - y))
            candidates.append(((x, y, bw, bh), 0.15))

        best: Optional[Tuple[OcrResult, List[AiMeasurement], Tuple[int, int, int, int], float, float]] = None
        for bbox, base_conf in candidates:
            x, y, bw, bh = bbox
            roi = frame[y : y + bh, x : x + bw]
            prepared = preprocess_roi(roi)
            ocr = self.ocr_engine.extract(prepared)
            measurements = self.parser.parse(ocr.text, confidence=ocr.confidence)
            text = ocr.text.lower()
            hint_score = 0.0
            if "pv" in text:
                hint_score += 0.8
            if "vmax" in text:
                hint_score += 0.8
            if "mmhg" in text:
                hint_score += 0.8
            candidate_score = (len(measurements) * 1.2) + hint_score + (ocr.confidence * 0.5)
            if best is None or candidate_score > best[4]:
                best = (ocr, measurements, bbox, base_conf, candidate_score)

        if best is None:
            return None, [], None, 0.0
        best_ocr, best_measurements, best_bbox, base_conf, best_score = best
        # Require some signal before accepting fallback output.
        if not best_measurements and best_score < 1.2:
            return None, [], None, 0.0
        return best_ocr, best_measurements, best_bbox, base_conf

    def _to_ai_result(self, records: List[MeasurementRecord]) -> AiResult:
        measurements = [
            AiMeasurement(
                name=record.measurement_name,
                value=record.measurement_value,
                unit=record.measurement_unit or None,
                source="echo_ocr_pipeline",
            )
            for record in records
        ]
        boxes = [
            OverlayBox(
                x=float(record.roi_bbox[0]),
                y=float(record.roi_bbox[1]),
                width=float(record.roi_bbox[2]),
                height=float(record.roi_bbox[3]),
                label="measurement_box",
                confidence=record.parser_confidence,
            )
            for record in records
        ]
        return AiResult(
            model_name=f"{self.name}:{self.ocr_engine.name}",
            created_at=datetime.utcnow(),
            boxes=boxes,
            measurements=measurements,
            raw={"record_count": len(records), "pipeline_version": self.version},
        )
