from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.io.dicom_reader import read_dataset
from app.models.types import AiMeasurement
from app.pipeline.measurements.measurement_decoder import canonicalize_exact_line
from app.pipeline.measurements.measurement_parsers import RegexMeasurementParser, postprocess_measurements


_TEXTUAL_MODALITIES = {"DOC", "OT", "PR", "SR"}
_TEXTUAL_VRS = {"LT", "ST", "UT"}
_INTERESTING_TEXT_KEYS = {
    "TextValue",
    "ImageComments",
    "ContentDescription",
    "StudyDescription",
    "SeriesDescription",
    "PerformedProcedureStepDescription",
    "InterpretationText",
    "ResultComments",
}

_UNIT_ALIASES = {
    "%": "%",
    "percent": "%",
    "mmhg": "mmHg",
    "mm[hg]": "mmHg",
    "millimeter of mercury": "mmHg",
    "millimetre of mercury": "mmHg",
    "cm": "cm",
    "centimeter": "cm",
    "centimetre": "cm",
    "mm": "mm",
    "millimeter": "mm",
    "millimetre": "mm",
    "ml": "ml",
    "milliliter": "ml",
    "millilitre": "ml",
    "m/s": "m/s",
    "meter per second": "m/s",
    "metre per second": "m/s",
    "cm/s": "cm/s",
    "centimeter per second": "cm/s",
    "centimetre per second": "cm/s",
    "ms": "ms",
    "millisecond": "ms",
    "milliseconds": "ms",
    "cm2": "cm2",
    "cm^2": "cm2",
    "square centimeter": "cm2",
    "square centimetre": "cm2",
    "ml/m2": "ml/m2",
    "ml/m^2": "ml/m2",
}


def _empty_notes() -> tuple[str, ...]:
    return ()


@dataclass(frozen=True)
class CompanionMeasurement:
    name: str
    value: str
    unit: str | None = None
    exact_line_text: str = ""
    order_hint: int | None = None
    confidence: float = 0.99
    source_kind: str = "study_companion"
    source_modality: str | None = None
    source_path: str = ""
    source_sop_instance_uid: str | None = None


@dataclass(frozen=True)
class StudyCompanionResult:
    measurements: tuple[CompanionMeasurement, ...] = field(default_factory=tuple)
    inspected_files: int = 0
    matched_files: int = 0
    notes: tuple[str, ...] = field(default_factory=_empty_notes)

    @property
    def has_measurements(self) -> bool:
        return bool(self.measurements)


class StudyCompanionDiscovery:
    def __init__(
        self,
        *,
        recursive: bool = True,
        max_files: int = 256,
    ) -> None:
        self.recursive = bool(recursive)
        self.max_files = max(1, int(max_files))
        self._text_parser = RegexMeasurementParser()

    def discover(self, dicom_path: Path, *, study_instance_uid: str | None = None) -> StudyCompanionResult:
        try:
            target_ds: Any = read_dataset(dicom_path, load_pixels=False)
        except Exception as exc:
            return StudyCompanionResult(notes=(f"target_read_failed:{exc}",))

        target_study_uid = study_instance_uid or _string_value(getattr(target_ds, "StudyInstanceUID", None))
        if not target_study_uid:
            return StudyCompanionResult(notes=("missing_target_study_uid",))

        inspected_files = 0
        matched_files = 0
        extracted: list[CompanionMeasurement] = []

        for candidate_path in self._candidate_paths(dicom_path):
            if candidate_path == dicom_path:
                continue
            inspected_files += 1
            try:
                candidate_ds: Any = read_dataset(candidate_path, load_pixels=False)
            except Exception:
                continue

            if _string_value(getattr(candidate_ds, "StudyInstanceUID", None)) != target_study_uid:
                continue

            matched_files += 1
            extracted.extend(self._extract_from_dataset(candidate_ds, candidate_path))

        if not extracted:
            return StudyCompanionResult(inspected_files=inspected_files, matched_files=matched_files)

        deduped = self._dedupe_measurements(extracted)
        return StudyCompanionResult(
            measurements=tuple(deduped),
            inspected_files=inspected_files,
            matched_files=matched_files,
        )

    def _candidate_paths(self, dicom_path: Path) -> list[Path]:
        root = dicom_path.parent
        iterator: Iterable[Path]
        if self.recursive:
            iterator = root.rglob("*.dcm")
        else:
            iterator = root.glob("*.dcm")
        paths = sorted({path.resolve() for path in iterator if path.is_file()})
        return paths[: self.max_files]

    def _extract_from_dataset(self, ds: Any, path: Path) -> list[CompanionMeasurement]:
        modality = _string_value(getattr(ds, "Modality", None)) or ""
        modality = modality.upper()
        source_sop_instance_uid = _string_value(getattr(ds, "SOPInstanceUID", None))
        sr_items = self._extract_sr_measurements(
            ds,
            path,
            modality=modality,
            source_sop_instance_uid=source_sop_instance_uid,
        )
        if sr_items:
            return sr_items
        if modality in _TEXTUAL_MODALITIES:
            return self._extract_textual_measurements(
                ds,
                path,
                modality=modality,
                source_sop_instance_uid=source_sop_instance_uid,
            )
        return []

    def _extract_sr_measurements(
        self,
        ds: Any,
        path: Path,
        *,
        modality: str,
        source_sop_instance_uid: str | None,
    ) -> list[CompanionMeasurement]:
        content = getattr(ds, "ContentSequence", None)
        if not content:
            return []

        extracted: list[CompanionMeasurement] = []
        for order, item in enumerate(content):
            extracted.extend(
                self._walk_sr_item(
                    item,
                    path=path,
                    modality=modality or "SR",
                    order_seed=order,
                    source_sop_instance_uid=source_sop_instance_uid,
                )
            )
        return extracted

    def _walk_sr_item(
        self,
        item: Any,
        *,
        path: Path,
        modality: str,
        order_seed: int,
        source_sop_instance_uid: str | None,
    ) -> list[CompanionMeasurement]:
        extracted: list[CompanionMeasurement] = []
        concept_name = self._concept_name(item)
        value_type = (_string_value(getattr(item, "ValueType", None)) or "").upper()
        numeric_payload = self._extract_numeric_payload(item)
        if concept_name and numeric_payload is not None:
            value, unit = numeric_payload
            exact_line = canonicalize_exact_line(" ".join(part for part in (concept_name, value, unit or "") if part))
            extracted.append(
                CompanionMeasurement(
                    name=concept_name,
                    value=value,
                    unit=unit,
                    exact_line_text=exact_line,
                    order_hint=order_seed,
                    confidence=0.995,
                    source_kind="study_companion_sr",
                    source_modality=modality or "SR",
                    source_path=str(path),
                    source_sop_instance_uid=source_sop_instance_uid,
                )
            )
        elif value_type == "TEXT":
            text_value = _string_value(getattr(item, "TextValue", None))
            if text_value:
                extracted.extend(
                    self._measurements_from_text(
                        text_value,
                        path=path,
                        modality=modality,
                        source_kind="study_companion_text",
                        source_sop_instance_uid=source_sop_instance_uid,
                    )
                )

        children = getattr(item, "ContentSequence", None) or []
        for child_index, child in enumerate(children):
            extracted.extend(
                self._walk_sr_item(
                    child,
                    path=path,
                    modality=modality or "SR",
                    order_seed=order_seed + child_index + 1,
                    source_sop_instance_uid=source_sop_instance_uid,
                )
            )
        return extracted

    def _extract_textual_measurements(
        self,
        ds: Any,
        path: Path,
        *,
        modality: str,
        source_sop_instance_uid: str | None,
    ) -> list[CompanionMeasurement]:
        chunks: list[str] = []
        self._collect_text_chunks(ds, chunks)
        if not chunks:
            return []
        return self._measurements_from_text(
            "\n".join(chunks),
            path=path,
            modality=modality,
            source_kind="study_companion_text",
            source_sop_instance_uid=source_sop_instance_uid,
        )

    def _collect_text_chunks(self, ds: Any, chunks: list[str]) -> None:
        for element in ds:
            keyword = str(getattr(element, "keyword", "") or "")
            vr = str(getattr(element, "VR", "") or "")
            value = getattr(element, "value", None)
            if keyword in _INTERESTING_TEXT_KEYS and isinstance(value, str):
                text = value.strip()
                if text:
                    chunks.append(text)
            elif vr in _TEXTUAL_VRS and isinstance(value, str):
                text = value.strip()
                if _looks_like_measurement_text(text):
                    chunks.append(text)

            if isinstance(value, list):
                for item in value:
                    if hasattr(item, "__iter__") and hasattr(item, "dir"):
                        self._collect_text_chunks(item, chunks)

    def _measurements_from_text(
        self,
        text: str,
        *,
        path: Path,
        modality: str,
        source_kind: str,
        source_sop_instance_uid: str | None,
    ) -> list[CompanionMeasurement]:
        parsed = self._text_parser.parse(text, confidence=0.94)
        if not parsed:
            return []
        processed = postprocess_measurements(parsed)
        items: list[CompanionMeasurement] = []
        for order, measurement in enumerate(processed):
            exact_line = canonicalize_exact_line(
                " ".join(part for part in (measurement.name, measurement.value, measurement.unit or "") if part)
            )
            items.append(
                CompanionMeasurement(
                    name=measurement.name,
                    value=measurement.value,
                    unit=measurement.unit,
                    exact_line_text=exact_line,
                    order_hint=order,
                    confidence=0.94,
                    source_kind=source_kind,
                    source_modality=modality,
                    source_path=str(path),
                    source_sop_instance_uid=source_sop_instance_uid,
                )
            )
        return items

    def _dedupe_measurements(self, items: list[CompanionMeasurement]) -> list[CompanionMeasurement]:
        ai_items = [
            AiMeasurement(
                name=item.name,
                value=item.value,
                unit=item.unit,
                source=f"{item.source_kind}:{item.source_path}",
                order_hint=item.order_hint,
            )
            for item in items
        ]
        normalized = postprocess_measurements(ai_items)
        remaining = list(items)
        deduped: list[CompanionMeasurement] = []
        for normalized_item in normalized:
            best_index = None
            best_score = -1.0
            for index, candidate in enumerate(remaining):
                score = 0.0
                if candidate.name == normalized_item.name:
                    score += 2.0
                if candidate.value == normalized_item.value:
                    score += 2.0
                if (candidate.unit or "") == (normalized_item.unit or ""):
                    score += 1.0
                score += candidate.confidence
                if score > best_score:
                    best_score = score
                    best_index = index
            if best_index is None:
                continue
            matched = remaining.pop(best_index)
            deduped.append(
                CompanionMeasurement(
                    name=normalized_item.name,
                    value=normalized_item.value,
                    unit=normalized_item.unit,
                    exact_line_text=canonicalize_exact_line(
                        " ".join(
                            part
                            for part in (normalized_item.name, normalized_item.value, normalized_item.unit or "")
                            if part
                        )
                    ),
                    order_hint=matched.order_hint,
                    confidence=matched.confidence,
                    source_kind=matched.source_kind,
                    source_modality=matched.source_modality,
                    source_path=matched.source_path,
                    source_sop_instance_uid=matched.source_sop_instance_uid,
                )
            )
        return deduped

    @staticmethod
    def _concept_name(item: Any) -> str | None:
        sequence = getattr(item, "ConceptNameCodeSequence", None)
        if not sequence:
            return None
        first = sequence[0]
        for field in ("CodeMeaning", "CodeValue", "LongCodeValue"):
            value = _string_value(getattr(first, field, None))
            if value:
                return value
        return None

    def _extract_numeric_payload(self, item: Any) -> tuple[str, str | None] | None:
        measured_value_sequence = getattr(item, "MeasuredValueSequence", None)
        if measured_value_sequence:
            first = measured_value_sequence[0]
            value = _string_value(getattr(first, "NumericValue", None)) or _string_value(getattr(first, "FloatingPointValue", None))
            if not value:
                return None
            unit = self._normalize_unit_sequence(getattr(first, "MeasurementUnitsCodeSequence", None))
            return value.replace(",", "."), unit

        numeric_value = _string_value(getattr(item, "NumericValue", None))
        if numeric_value:
            unit = self._normalize_unit_sequence(getattr(item, "MeasurementUnitsCodeSequence", None))
            return numeric_value.replace(",", "."), unit
        return None

    def _normalize_unit_sequence(self, sequence: Any) -> str | None:
        if not sequence:
            return None
        first = sequence[0]
        raw_candidates = [
            _string_value(getattr(first, "CodeValue", None)),
            _string_value(getattr(first, "CodeMeaning", None)),
            _string_value(getattr(first, "LongCodeValue", None)),
        ]
        for candidate in raw_candidates:
            if not candidate:
                continue
            normalized = _UNIT_ALIASES.get(candidate.strip().lower())
            if normalized:
                return normalized
            canonical = candidate.strip().replace(" ", "")
            if canonical in {"%", "cm", "mm", "ml", "ms", "m/s", "cm/s", "cm2", "ml/m2", "mmHg"}:
                return canonical
        return None


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_measurement_text(text: str) -> bool:
    lowered = text.lower()
    has_digit = any(char.isdigit() for char in lowered)
    has_letter = any(char.isalpha() for char in lowered)
    if not has_digit or not has_letter:
        return False
    return any(unit in lowered for unit in ("mmhg", "m/s", "cm", "mm", "%", "ml"))
