from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.io.dicom_loader import load_dicom_series
from app.ocr.preprocessing import preprocess_roi
from app.pipeline.echo_ocr_box_detector import TopLeftBlueGrayBoxDetector
from app.pipeline.measurement_parsers import (
    LocalLlmMeasurementParser,
    LocalLlmParserConfig,
    _postprocess_measurements,
)
from app.pipeline.ocr_engines import build_engine
from app.repo_paths import DEFAULT_EXACT_LINES_PATH
from app.validation.datasets import parse_labels
from app.validation.evaluation import run_evaluation

HEADER_TRIM_PX = 0
DATASET_TASK = "exact_roi_measurement_transcription"
_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_LINE_PARSE_RE = re.compile(
    r"""
    ^
    (?:(?P<prefix>\d+)\s+)?
    (?P<label>.*?)
    (?:
        \s+(?P<value>[-+]?\d+(?:[.,]\d+)?)
        (?:\s*(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2))?
    )?
    $
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().replace(",", ".")


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = unit.strip()
    if not cleaned:
        return None
    aliases = {
        "mmhg": "mmHg",
        "m/s": "m/s",
        "cm/s": "cm/s",
        "m/s2": "m/s2",
        "cm": "cm",
        "mm": "mm",
        "ms": "ms",
        "s": "s",
        "%": "%",
        "ml": "ml",
        "cm2": "cm2",
        "ml/m2": "ml/m2",
        "bpm": "bpm",
    }
    return aliases.get(cleaned.lower(), cleaned)


def _canonicalize_line(text: str) -> str:
    line = _normalize_space(text)
    line = line.replace("\\,", " ")
    line = line.replace("\\%", " %")
    line = re.sub(r"\\text\{([^}]*)\}", r"\1", line)
    line = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", line)
    line = re.sub(r"(\d)(%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)\b", r"\1 \2", line)
    return _normalize_space(line)


@dataclass
class StructuredLine:
    line: str
    prefix: str | None
    label: str | None
    value: str | None
    unit: str | None


def _parse_line(text: str) -> StructuredLine:
    line = _canonicalize_line(text)
    match = _LINE_PARSE_RE.match(line)
    if match is None:
        return StructuredLine(line=line, prefix=None, label=line or None, value=None, unit=None)

    prefix = match.group("prefix")
    label = _normalize_space(match.group("label") or "") or None
    value = _normalize_value(match.group("value"))
    unit = _normalize_unit(match.group("unit"))

    return StructuredLine(
        line=line,
        prefix=prefix,
        label=label,
        value=value,
        unit=unit,
    )


def _values_match(predicted: str | None, expected: str | None, tolerance: float = 0.011) -> bool:
    if predicted is None or expected is None:
        return predicted == expected
    try:
        return abs(float(predicted) - float(expected)) <= tolerance
    except Exception:
        return predicted.strip() == expected.strip()


def _string_equal(a: str | None, b: str | None) -> bool:
    return _normalize_space(a or "").lower() == _normalize_space(b or "").lower()


def _prediction_to_line(prediction: dict[str, str | None]) -> StructuredLine:
    parts = [
        str(prediction.get("name") or "").strip(),
        str(prediction.get("value") or "").strip(),
        str(prediction.get("unit") or "").strip(),
    ]
    return _parse_line(" ".join(part for part in parts if part))


def _label_to_line(label: Any) -> StructuredLine:
    return _parse_line(str(getattr(label, "text", "")))


def _score_line_pair(expected_text: str, predicted_text: str) -> tuple[int, dict[str, bool]]:
    expected = _parse_line(expected_text)
    predicted = _parse_line(predicted_text)

    exact = _string_equal(predicted.line, expected.line)
    prefix = _string_equal(predicted.prefix, expected.prefix)
    label = _string_equal(predicted.label, expected.label)
    value = _values_match(predicted.value, expected.value)
    unit = _string_equal(predicted.unit, expected.unit)

    score = 0
    if exact:
        score += 100
    if prefix:
        score += 8
    if label:
        score += 4
    if value:
        score += 2
    if unit:
        score += 1

    return score, {
        "exact_match": exact,
        "prefix_match": prefix,
        "label_match": label,
        "value_match": value,
        "unit_match": unit,
    }


@dataclass
class RawEvalScores:
    total_files: int
    files_with_text: int
    total_labels: int
    exact_hits: int
    value_hits: int
    label_hits: int
    prefix_hits: int
    elapsed_s: float

    @property
    def text_detect_rate(self) -> float:
        return self.files_with_text / max(self.total_files, 1)

    @property
    def exact_hit_rate(self) -> float:
        return self.exact_hits / max(self.total_labels, 1)

    @property
    def value_hit_rate(self) -> float:
        return self.value_hits / max(self.total_labels, 1)

    @property
    def label_hit_rate(self) -> float:
        return self.label_hits / max(self.total_labels, 1)

    @property
    def prefix_hit_rate(self) -> float:
        return self.prefix_hits / max(self.total_labels, 1)


@dataclass
class DetailedLineResult:
    expected_line: str
    actual_line: str | None
    exact_match: bool
    prefix_match: bool
    label_match: bool
    value_match: bool
    unit_match: bool
    error_type: str


@dataclass
class FrameDebugInfo:
    frame_index: int
    roi_present: bool
    roi_bbox: tuple[int, int, int, int] | None
    ocr_bbox: tuple[int, int, int, int] | None
    roi_confidence: float
    raw_text: str


@dataclass
class FileDebugRecord:
    label_set: str
    labels_path: str
    engine: str
    mode: str
    file_path: str
    file_name: str
    total_labels: int
    exact_matches: int
    value_matches: int
    label_matches: int
    prefix_matches: int
    text_present: bool
    roi_frames: list[FrameDebugInfo]
    expected_lines: list[str]
    predicted_lines: list[str]
    mismatches: list[DetailedLineResult]
    roi_visualizations: list[str] | None = None


def _classify_mismatch(
    *,
    actual_present: bool,
    exact_match: bool,
    prefix_match: bool,
    label_match: bool,
    value_match: bool,
    unit_match: bool,
) -> str:
    if exact_match:
        return "exact_match"
    if not actual_present:
        return "missing_prediction"
    if label_match and value_match and unit_match and not prefix_match:
        return "wrong_prefix"
    if label_match and value_match and not unit_match:
        return "wrong_unit"
    if label_match and not value_match:
        return "wrong_value"
    if value_match and not label_match:
        return "wrong_label_for_value"
    if prefix_match and label_match and not value_match:
        return "wrong_value"
    return "wrong_line"


def _json_ready_file_debug_record(record: FileDebugRecord) -> dict[str, Any]:
    data = asdict(record)
    for frame in data["roi_frames"]:
        bbox = frame.get("roi_bbox")
        if bbox is not None:
            frame["roi_bbox"] = list(bbox)
        ocr_bbox = frame.get("ocr_bbox")
        if ocr_bbox is not None:
            frame["ocr_bbox"] = list(ocr_bbox)
    return data


def _best_raw_line_match(expected_line: str, predicted_lines: list[str]) -> DetailedLineResult:
    if not predicted_lines:
        return DetailedLineResult(
            expected_line=expected_line,
            actual_line=None,
            exact_match=False,
            prefix_match=False,
            label_match=False,
            value_match=False,
            unit_match=False,
            error_type="missing_prediction",
        )

    best_line: str | None = None
    best_score = -1
    best_flags: dict[str, bool] | None = None

    for line in predicted_lines:
        score, flags = _score_line_pair(expected_line, line)
        if score > best_score:
            best_score = score
            best_line = line
            best_flags = flags
        if flags["exact_match"]:
            break

    assert best_flags is not None

    return DetailedLineResult(
        expected_line=expected_line,
        actual_line=best_line,
        exact_match=best_flags["exact_match"],
        prefix_match=best_flags["prefix_match"],
        label_match=best_flags["label_match"],
        value_match=best_flags["value_match"],
        unit_match=best_flags["unit_match"],
        error_type=_classify_mismatch(
            actual_present=best_line is not None,
            exact_match=best_flags["exact_match"],
            prefix_match=best_flags["prefix_match"],
            label_match=best_flags["label_match"],
            value_match=best_flags["value_match"],
            unit_match=best_flags["unit_match"],
        ),
    )


def _save_roi_visualization_image(
    frame,
    detection,
    destination: Path,
    *,
    title: str,
    ocr_bbox: tuple[int, int, int, int] | None = None,
) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        import numpy as np
    except Exception:
        return

    rgb_frame = frame
    if getattr(frame, "ndim", 0) == 2:
        rgb_frame = np.stack([frame, frame, frame], axis=-1)
    elif getattr(frame, "ndim", 0) == 3 and frame.shape[-1] >= 3:
        rgb_frame = frame[..., :3]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(rgb_frame)
    ax.set_title(title)
    ax.axis("off")

    if detection.present and detection.bbox is not None:
        x, y, w, h = detection.bbox
        rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor="lime", facecolor="none")
        ax.add_patch(rect)
        ax.text(
            x,
            max(0, y - 3),
            f"ROI ({x}, {y}, {w}, {h}) conf={detection.confidence:.3f}",
            color="lime",
            fontsize=10,
            fontweight="bold",
            bbox={"facecolor": "black", "alpha": 0.55, "pad": 2},
        )

    if ocr_bbox is not None:
        ox, oy, ow, oh = ocr_bbox
        ocr_rect = patches.Rectangle(
            (ox, oy),
            ow,
            oh,
            linewidth=2,
            edgecolor="cyan",
            facecolor="none",
            linestyle="--",
        )
        ax.add_patch(ocr_rect)
        ax.text(
            ox,
            min(oy + 3, oy + oh - 2),
            f"OCR ({ox}, {oy}, {ow}, {oh})",
            color="cyan",
            fontsize=10,
            fontweight="bold",
            bbox={"facecolor": "black", "alpha": 0.55, "pad": 2},
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def _sanitize_filename(text: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return sanitized.strip("._") or "item"


def _relative_to_output(path: Path, output_dir: Path) -> str:
    try:
        return str(path.relative_to(output_dir))
    except Exception:
        return str(path)


def _save_roi_visualizations_for_record(
    *,
    output_dir: Path,
    root_dir: Path,
    label_set: str,
    engine_name: str,
    mode_name: str,
    file_record: dict[str, Any],
    limit: int,
    counter_key: tuple[str, str, str],
    counts: dict[tuple[str, str, str], int],
) -> list[str]:
    if limit > 0 and counts.get(counter_key, 0) >= limit:
        return []

    file_path = Path(str(file_record.get("file_path", "")))
    if not file_path.exists():
        return []

    roi_frames = file_record.get("roi_frames", [])
    if not isinstance(roi_frames, list) or not roi_frames:
        return []

    try:
        series = load_dicom_series(file_path, load_pixels=True)
    except Exception:
        return []

    saved_paths: list[str] = []
    safe_file_name = _sanitize_filename(str(file_record.get("file_name", file_path.stem)))

    for frame_info in roi_frames:
        if limit > 0 and counts.get(counter_key, 0) >= limit:
            break
        if not isinstance(frame_info, dict):
            continue
        if not frame_info.get("roi_present", False):
            continue

        frame_index = int(frame_info.get("frame_index", -1))
        if frame_index < 0 or frame_index >= series.frame_count:
            continue

        bbox = frame_info.get("roi_bbox")
        ocr_bbox = frame_info.get("ocr_bbox")
        detection = type(
            "_DetectionProxy",
            (),
            {
                "present": bbox is not None,
                "bbox": tuple(bbox) if isinstance(bbox, list) else bbox,
                "confidence": float(frame_info.get("roi_confidence", 0.0)),
            },
        )()

        frame = series.get_frame(frame_index)
        destination = (
            root_dir
            / _sanitize_filename(label_set)
            / _sanitize_filename(engine_name)
            / _sanitize_filename(mode_name)
            / f"{safe_file_name}__frame_{frame_index:03d}.png"
        )
        _save_roi_visualization_image(
            frame,
            detection,
            destination,
            title=f"{label_set} | {engine_name} | {mode_name} | {file_path.name} | frame={frame_index}",
            ocr_bbox=tuple(ocr_bbox) if isinstance(ocr_bbox, list) else ocr_bbox,
        )
        saved_paths.append(_relative_to_output(destination, output_dir))
        counts[counter_key] = counts.get(counter_key, 0) + 1

    return saved_paths


def _html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _render_html_report(rows: list[dict[str, Any]], *, title: str) -> str:
    sections: list[str] = []
    grouped_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("label_set", "")),
            str(row.get("engine", "")),
            str(row.get("mode", "")),
        )
        grouped_rows.setdefault(key, []).append(row)

    for (label_set, engine_name, mode_name), items in grouped_rows.items():
        section_parts = [
            "<section class=\"group\">",
            f"<h2>{_html_escape(label_set)} / {_html_escape(engine_name)} / {_html_escape(mode_name)}</h2>",
        ]
        for item in items:
            mismatches = item.get("mismatches", [])
            predicted_lines = item.get("predicted_lines", [])
            roi_frames = item.get("roi_frames", [])
            roi_images = item.get("roi_visualizations", [])

            card_parts = [
                "<article class=\"file-card\">",
                f"<h3>{_html_escape(item.get('file_name', ''))}</h3>",
                "<div class=\"meta\">",
                f"<div><strong>File:</strong> {_html_escape(item.get('file_path', ''))}</div>",
                f"<div><strong>Labels:</strong> {_html_escape(item.get('total_labels', 0))}</div>",
                f"<div><strong>Exact matches:</strong> {_html_escape(item.get('exact_matches', 0))}</div>",
                f"<div><strong>Value matches:</strong> {_html_escape(item.get('value_matches', 0))}</div>",
                f"<div><strong>Label matches:</strong> {_html_escape(item.get('label_matches', 0))}</div>",
                f"<div><strong>Prefix matches:</strong> {_html_escape(item.get('prefix_matches', 0))}</div>",
                f"<div><strong>Text present:</strong> {_html_escape(item.get('text_present', False))}</div>",
                "</div>",
                "<div class=\"columns\">",
                "<div>",
                "<h4>Expected lines</h4>",
                "<ul>",
            ]
            for expected in item.get("expected_lines", []):
                card_parts.append(f"<li><code>{_html_escape(expected)}</code></li>")
            card_parts.extend(["</ul>", "</div>", "<div>", "<h4>Predicted lines</h4>", "<ul>"])
            if predicted_lines:
                for prediction in predicted_lines:
                    card_parts.append(f"<li><code>{_html_escape(prediction)}</code></li>")
            else:
                card_parts.append("<li><code>NO PREDICTIONS</code></li>")
            card_parts.extend(["</ul>", "</div>", "</div>"])

            card_parts.append("<h4>Mismatches</h4>")
            if mismatches:
                card_parts.append(
                    "<table><thead><tr><th>Type</th><th>Expected</th><th>Actual</th></tr></thead><tbody>"
                )
                for mismatch in mismatches:
                    card_parts.append(
                        "<tr>"
                        f"<td>{_html_escape(mismatch.get('error_type', 'unknown'))}</td>"
                        f"<td><code>{_html_escape(mismatch.get('expected_line', ''))}</code></td>"
                        f"<td><code>{_html_escape(mismatch.get('actual_line') or 'NOT FOUND')}</code></td>"
                        "</tr>"
                    )
                card_parts.append("</tbody></table>")
            else:
                card_parts.append("<p class=\"ok\">No mismatches.</p>")

            card_parts.append("<h4>ROI frames</h4>")
            if roi_frames:
                card_parts.append(
                    "<table><thead><tr><th>Frame</th><th>Present</th><th>BBox</th><th>Confidence</th></tr></thead><tbody>"
                )
                for frame in roi_frames:
                    card_parts.append(
                        "<tr>"
                        f"<td>{_html_escape(frame.get('frame_index'))}</td>"
                        f"<td>{_html_escape(frame.get('roi_present'))}</td>"
                        f"<td><code>{_html_escape(frame.get('roi_bbox'))}</code></td>"
                        f"<td>{_html_escape(frame.get('roi_confidence'))}</td>"
                        "</tr>"
                    )
                card_parts.append("</tbody></table>")
            else:
                card_parts.append("<p>No ROI frame information.</p>")

            if roi_images:
                card_parts.append("<h4>ROI visualizations</h4><div class=\"gallery\">")
                for image_path in roi_images:
                    card_parts.append(
                        "<figure>"
                        f"<a href=\"{_html_escape(image_path)}\" target=\"_blank\">"
                        f"<img src=\"{_html_escape(image_path)}\" alt=\"ROI visualization\">"
                        "</a>"
                        f"<figcaption>{_html_escape(image_path)}</figcaption>"
                        "</figure>"
                    )
                card_parts.append("</div>")

            card_parts.append("</article>")
            section_parts.extend(card_parts)

        section_parts.append("</section>")
        sections.append("\n".join(section_parts))

    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{_html_escape(title)}</title>\n"
        "  <style>\n"
        "    body { font-family: Arial, sans-serif; margin: 24px; background: #f6f8fa; color: #222; }\n"
        "    h1, h2, h3, h4 { margin-top: 0; }\n"
        "    .group { margin-bottom: 40px; }\n"
        "    .file-card { background: white; border: 1px solid #d0d7de; border-radius: 10px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }\n"
        "    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 16px; }\n"
        "    .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }\n"
        "    table { width: 100%; border-collapse: collapse; margin: 10px 0 16px; }\n"
        "    th, td { border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }\n"
        "    th { background: #f0f3f6; }\n"
        "    code { background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }\n"
        "    .gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }\n"
        "    .gallery img { width: 100%; height: auto; border: 1px solid #d0d7de; border-radius: 8px; background: white; }\n"
        "    .gallery figure { margin: 0; }\n"
        "    .gallery figcaption { font-size: 12px; color: #57606a; margin-top: 6px; word-break: break-all; }\n"
        "    .ok { color: #1a7f37; font-weight: 600; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{_html_escape(title)}</h1>\n"
        "  <p>Per-file OCR evaluation with exact displayed lines, mismatches, ROI metadata, and saved ROI visualizations.</p>\n"
        f"  {''.join(sections)}\n"
        "</body>\n"
        "</html>\n"
    )


def run_raw_text_eval(labels, engine) -> tuple[RawEvalScores, list[FileDebugRecord]]:
    detector = TopLeftBlueGrayBoxDetector()

    total_files = 0
    files_with_text = 0
    total_labels = 0
    exact_hits = 0
    value_hits = 0
    label_hits = 0
    prefix_hits = 0
    file_debug_records: list[FileDebugRecord] = []

    started = time.perf_counter()

    for labeled_file in labels:
        if not labeled_file.path.exists():
            continue

        total_files += 1
        total_labels += len(labeled_file.measurements)

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception:
            continue

        file_has_text = False
        all_lines: list[str] = []
        roi_frames: list[FrameDebugInfo] = []

        for frame_idx in range(series.frame_count):
            frame = series.get_frame(frame_idx)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                roi_frames.append(
                    FrameDebugInfo(
                        frame_index=frame_idx,
                        roi_present=False,
                        roi_bbox=None,
                        ocr_bbox=None,
                        roi_confidence=float(detection.confidence),
                        raw_text="",
                    )
                )
                continue

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            ocr_bbox = (x, y, bw, bh)
            if HEADER_TRIM_PX > 0 and roi.shape[0] > HEADER_TRIM_PX:
                roi = roi[HEADER_TRIM_PX:, :]
                ocr_bbox = (x, y + HEADER_TRIM_PX, bw, bh - HEADER_TRIM_PX)

            prepared = preprocess_roi(roi)
            ocr_result = engine.extract(prepared)
            text = (ocr_result.text or "").strip()

            roi_frames.append(
                FrameDebugInfo(
                    frame_index=frame_idx,
                    roi_present=True,
                    roi_bbox=detection.bbox,
                    ocr_bbox=ocr_bbox,
                    roi_confidence=float(detection.confidence),
                    raw_text=text,
                )
            )

            if text:
                file_has_text = True
                all_lines.extend(_canonicalize_line(line) for line in text.splitlines() if line.strip())

        if file_has_text:
            files_with_text += 1

        mismatches: list[DetailedLineResult] = []
        local_exact_hits = 0
        local_value_hits = 0
        local_label_hits = 0
        local_prefix_hits = 0

        for measurement in labeled_file.measurements:
            expected_line = _canonicalize_line(measurement.text)
            detail = _best_raw_line_match(expected_line, all_lines)

            if detail.exact_match:
                exact_hits += 1
                local_exact_hits += 1
            if detail.value_match:
                value_hits += 1
                local_value_hits += 1
            if detail.label_match:
                label_hits += 1
                local_label_hits += 1
            if detail.prefix_match:
                prefix_hits += 1
                local_prefix_hits += 1
            if not detail.exact_match:
                mismatches.append(detail)

        file_debug_records.append(
            FileDebugRecord(
                label_set="",
                labels_path="",
                engine=getattr(engine, "name", type(engine).__name__),
                mode="raw_no_parser",
                file_path=str(labeled_file.path),
                file_name=labeled_file.file_name,
                total_labels=len(labeled_file.measurements),
                exact_matches=local_exact_hits,
                value_matches=local_value_hits,
                label_matches=local_label_hits,
                prefix_matches=local_prefix_hits,
                text_present=file_has_text,
                roi_frames=roi_frames,
                expected_lines=[_canonicalize_line(item.text) for item in labeled_file.measurements],
                predicted_lines=all_lines,
                mismatches=mismatches,
            )
        )

    elapsed_s = time.perf_counter() - started

    return RawEvalScores(
        total_files=total_files,
        files_with_text=files_with_text,
        total_labels=total_labels,
        exact_hits=exact_hits,
        value_hits=value_hits,
        label_hits=label_hits,
        prefix_hits=prefix_hits,
        elapsed_s=elapsed_s,
    ), file_debug_records


def format_rate(value: float) -> str:
    return f"{value:.1%}"


def _parser_label(parser_mode: str) -> str:
    if parser_mode == "regex":
        return "regex_parser"
    if parser_mode == "local_llm":
        return "local_llm_parser"
    return f"{parser_mode}_parser"


def _labels_label(labels_path: Path) -> str:
    return labels_path.stem


def _split_csv_arg(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _coerce_value_and_unit(value: str, unit: str | None) -> tuple[str, str | None]:
    cleaned_value = value.strip().replace(",", ".")
    cleaned_unit = (unit or "").strip() or None
    if cleaned_unit:
        return cleaned_value, cleaned_unit
    match = re.fullmatch(
        r"(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>%|mmHg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)?",
        cleaned_value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return cleaned_value, cleaned_unit
    parsed_value = str(match.group("value") or "").strip()
    parsed_unit = str(match.group("unit") or "").strip() or None
    return parsed_value, parsed_unit


def _vision_prompt() -> str:
    return (
        "You extract echocardiogram measurements from the attached image.\n"
        "Return ONLY valid JSON: an array of objects with keys "
        "\"name\", \"value\", \"unit\".\n"
        "Rules:\n"
        "- Extract only actual measurements from the measurement box overlay.\n"
        "- Preserve visible numeric row prefixes like 1, 2, 3 as part of the name when present.\n"
        "- Ignore telemetry, timestamps, gain, frequency, depth, frame counters, and other UI text.\n"
        "- value must be a numeric string.\n"
        "- unit may be \"\", \"%\", \"mmHg\", \"cm/s\", \"m/s\", \"cm\", \"mm\", \"ms\", \"s\", \"bpm\", \"ml/m2\", \"cm2\", or \"ml\".\n"
        "- Do not include commentary.\n"
    )


def _ollama_is_healthy(base_url: str) -> bool:
    request = Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
    try:
        with urlopen(request, timeout=2.0) as response:
            status = getattr(response, "status", 200)
            return int(status) < 500
    except (TimeoutError, URLError, ValueError):
        return False


def _available_ollama_models(base_url: str) -> list[str]:
    request = Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
    with urlopen(request, timeout=5.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        name = str(model.get("name", "")).strip()
        if name:
            names.append(name)
    return names


def _select_vision_model(explicit_model: str, base_url: str) -> str:
    if explicit_model.strip():
        return explicit_model.strip()
    candidates = _available_ollama_models(base_url)
    for name in candidates:
        lowered = name.lower()
        if any(token in lowered for token in ("vl", "vision", "llava", "moondream", "minicpm-v")):
            return name
    raise RuntimeError(
        "No local vision-capable Ollama model found. Pass --local-llm-only-model to choose one."
    )


def _call_vision_model(image, *, model: str, ollama_url: str, timeout_s: float) -> str:
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Failed to encode ROI for local vision LLM evaluation.")
    payload = json.dumps(
        {
            "model": model,
            "prompt": _vision_prompt(),
            "images": [base64.b64encode(encoded).decode("utf-8")],
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        f"{ollama_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Ollama vision request failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama vision request failed: {exc}") from exc
    return str(data.get("response", "") or "").strip()


def _parse_vision_predictions(payload: str, *, model: str) -> list[dict[str, str | None]]:
    from app.models.types import AiMeasurement

    parser = LocalLlmMeasurementParser(config=LocalLlmParserConfig(model=model))
    rows = parser._parse_json_payload(payload)
    parsed_items: list[AiMeasurement] = []
    for idx, row in enumerate(rows):
        name = str(row.get("name", "")).strip()
        value = str(row.get("value", "")).strip()
        unit = str(row.get("unit", "")).strip() or None
        if not name or not value:
            continue
        coerced_value, coerced_unit = _coerce_value_and_unit(value, unit)
        parsed_items.append(
            AiMeasurement(
                name=name,
                value=coerced_value,
                unit=coerced_unit,
                source=f"local_vision_llm:{model}",
                order_hint=idx,
            )
        )
    items = _postprocess_measurements(parsed_items)
    return [{"name": item.name, "value": item.value, "unit": item.unit} for item in items]


def _match_predictions_to_expected(
    expected_lines: list[str], predictions: list[dict[str, str | None]]
) -> list[DetailedLineResult]:
    predicted_lines = [_prediction_to_line(item).line for item in predictions]
    used_indices: set[int] = set()
    results: list[DetailedLineResult] = []

    for expected_line in expected_lines:
        best_idx: int | None = None
        best_score = -1
        best_detail: DetailedLineResult | None = None

        for idx, predicted_line in enumerate(predicted_lines):
            if idx in used_indices:
                continue
            score, flags = _score_line_pair(expected_line, predicted_line)
            detail = DetailedLineResult(
                expected_line=expected_line,
                actual_line=predicted_line,
                exact_match=flags["exact_match"],
                prefix_match=flags["prefix_match"],
                label_match=flags["label_match"],
                value_match=flags["value_match"],
                unit_match=flags["unit_match"],
                error_type=_classify_mismatch(
                    actual_present=True,
                    exact_match=flags["exact_match"],
                    prefix_match=flags["prefix_match"],
                    label_match=flags["label_match"],
                    value_match=flags["value_match"],
                    unit_match=flags["unit_match"],
                ),
            )
            if score > best_score:
                best_score = score
                best_idx = idx
                best_detail = detail
            if flags["exact_match"]:
                break

        if best_detail is None or best_idx is None:
            results.append(
                DetailedLineResult(
                    expected_line=expected_line,
                    actual_line=None,
                    exact_match=False,
                    prefix_match=False,
                    label_match=False,
                    value_match=False,
                    unit_match=False,
                    error_type="missing_prediction",
                )
            )
        else:
            used_indices.add(best_idx)
            results.append(best_detail)

    return results


def run_local_vision_llm_eval(
    labels,
    *,
    model: str,
    ollama_url: str,
    timeout_s: float,
) -> tuple[dict[str, float], list[FileDebugRecord]]:
    detector = TopLeftBlueGrayBoxDetector()

    total_labels = 0
    total_exact_match = 0
    total_value_match = 0
    total_label_match = 0
    total_prefix_match = 0
    total_detected = 0
    total_files = 0
    total_files_with_text = 0
    elapsed_total = 0.0
    file_debug_records: list[FileDebugRecord] = []

    for labeled_file in labels:
        if not labeled_file.path.exists():
            continue

        total_files += 1
        total_labels += len(labeled_file.measurements)
        started = time.perf_counter()

        try:
            series = load_dicom_series(labeled_file.path, load_pixels=True)
        except Exception:
            elapsed_total += time.perf_counter() - started
            continue

        all_predictions: list[dict[str, str | None]] = []
        roi_frames: list[FrameDebugInfo] = []

        for frame_idx in range(series.frame_count):
            frame = series.get_frame(frame_idx)
            detection = detector.detect(frame)
            if not detection.present or detection.bbox is None:
                roi_frames.append(
                    FrameDebugInfo(
                        frame_index=frame_idx,
                        roi_present=False,
                        roi_bbox=None,
                        ocr_bbox=None,
                        roi_confidence=float(detection.confidence),
                        raw_text="",
                    )
                )
                continue

            x, y, bw, bh = detection.bbox
            roi = frame[y : y + bh, x : x + bw]
            ocr_bbox = (x, y, bw, bh)
            if HEADER_TRIM_PX > 0 and roi.shape[0] > HEADER_TRIM_PX:
                roi = roi[HEADER_TRIM_PX:, :]
                ocr_bbox = (x, y + HEADER_TRIM_PX, bw, bh - HEADER_TRIM_PX)

            prepared = preprocess_roi(roi)
            payload = _call_vision_model(
                prepared,
                model=model,
                ollama_url=ollama_url,
                timeout_s=timeout_s,
            )
            roi_frames.append(
                FrameDebugInfo(
                    frame_index=frame_idx,
                    roi_present=True,
                    roi_bbox=detection.bbox,
                    ocr_bbox=ocr_bbox,
                    roi_confidence=float(detection.confidence),
                    raw_text=payload,
                )
            )
            all_predictions.extend(_parse_vision_predictions(payload, model=model))

        elapsed_total += time.perf_counter() - started
        if all_predictions:
            total_files_with_text += 1

        expected_lines = [_canonicalize_line(item.text) for item in labeled_file.measurements]
        detailed_results = _match_predictions_to_expected(expected_lines, all_predictions)

        total_exact_match += sum(1 for result in detailed_results if result.exact_match)
        total_value_match += sum(1 for result in detailed_results if result.value_match)
        total_label_match += sum(1 for result in detailed_results if result.label_match)
        total_prefix_match += sum(1 for result in detailed_results if result.prefix_match)
        total_detected += len(all_predictions)

        file_debug_records.append(
            FileDebugRecord(
                label_set="",
                labels_path="",
                engine=model,
                mode="local_vision_llm_only",
                file_path=str(labeled_file.path),
                file_name=labeled_file.file_name,
                total_labels=len(labeled_file.measurements),
                exact_matches=sum(1 for result in detailed_results if result.exact_match),
                value_matches=sum(1 for result in detailed_results if result.value_match),
                label_matches=sum(1 for result in detailed_results if result.label_match),
                prefix_matches=sum(1 for result in detailed_results if result.prefix_match),
                text_present=bool(all_predictions),
                roi_frames=roi_frames,
                expected_lines=expected_lines,
                predicted_lines=[_prediction_to_line(item).line for item in all_predictions],
                mismatches=[result for result in detailed_results if not result.exact_match],
            )
        )

    return {
        "total_labels": float(total_labels),
        "total_exact_match": float(total_exact_match),
        "total_value_match": float(total_value_match),
        "total_label_match": float(total_label_match),
        "total_prefix_match": float(total_prefix_match),
        "total_predicted": float(total_detected),
        "total_files": float(total_files),
        "total_files_with_text": float(total_files_with_text),
        "exact_match_rate": total_exact_match / max(total_labels, 1),
        "value_match_rate": total_value_match / max(total_labels, 1),
        "label_match_rate": total_label_match / max(total_labels, 1),
        "prefix_match_rate": total_prefix_match / max(total_labels, 1),
        "text_detect_rate": total_files_with_text / max(total_files, 1),
        "elapsed_s": elapsed_total,
    }, file_debug_records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OCR engine comparison matrix on exact-line JSON labels"
    )
    parser.add_argument(
        "--labels",
        default=str(DEFAULT_EXACT_LINES_PATH),
        help="Path to the canonical JSON label file",
    )
    parser.add_argument(
        "--split",
        default="",
        help="Optional comma separated split filter (e.g. train,validation)",
    )
    parser.add_argument(
        "--engines",
        default="glm-ocr,surya,easyocr,tesseract,paddleocr",
        help="Comma separated engines",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "logs" / "ocr_engine_comparison"),
        help="Directory for CSV/JSON/Markdown outputs",
    )
    parser.add_argument(
        "--write-detailed-report",
        action="store_true",
        help="Write per-file detailed JSON outputs.",
    )
    parser.add_argument(
        "--detailed-report-name",
        default="ocr_engine_matrix_detailed.json",
        help="Filename for the per-file JSON report.",
    )
    parser.add_argument(
        "--write-detailed-markdown",
        action="store_true",
        help="Write a human-readable per-file markdown report.",
    )
    parser.add_argument(
        "--detailed-markdown-name",
        default="ocr_engine_matrix_detailed.md",
        help="Filename for the per-file markdown report.",
    )
    parser.add_argument(
        "--write-html-report",
        action="store_true",
        help="Write an HTML report with per-file outputs and ROI image previews.",
    )
    parser.add_argument(
        "--html-report-name",
        default="ocr_engine_matrix_detailed.html",
        help="Filename for the detailed HTML report.",
    )
    parser.add_argument(
        "--save-roi-visualizations",
        action="store_true",
        help="Save ROI visualization images for qualitative inspection.",
    )
    parser.add_argument(
        "--roi-visualization-dirname",
        default="roi_visualizations",
        help="Subdirectory inside --output-dir where ROI visualization images are stored.",
    )
    parser.add_argument(
        "--roi-visualization-limit",
        type=int,
        default=0,
        help="Maximum number of ROI images to save per engine/mode/label-set; 0 means no limit.",
    )
    parser.add_argument(
        "--parser-modes",
        default="regex",
        help="Comma separated parser modes to benchmark (e.g. regex,local_llm)",
    )
    parser.add_argument(
        "--skip-raw",
        action="store_true",
        help="Skip raw OCR text evaluation and only run parser modes.",
    )
    parser.add_argument(
        "--local-llm-only",
        action="store_true",
        help="Benchmark a local vision-capable LLM directly on the ROI image without OCR.",
    )
    parser.add_argument(
        "--local-llm-only-model",
        default="",
        help="Override the Ollama vision model used by --local-llm-only.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Base URL for the local Ollama server.",
    )
    parser.add_argument(
        "--local-llm-timeout",
        type=float,
        default=60.0,
        help="Timeout per local vision LLM frame request in seconds.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    engines = [name.strip() for name in args.engines.split(",") if name.strip()]
    parser_modes = [name.strip() for name in args.parser_modes.split(",") if name.strip()]
    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise SystemExit(f"Labels file not found: {labels_path}")

    split_filter = {
        item.strip().lower()
        for item in args.split.split(",")
        if item.strip()
    }

    rows: list[dict[str, Any]] = []
    detailed_rows: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    roi_visualization_root = output_dir / args.roi_visualization_dirname
    roi_visualization_counts: dict[tuple[str, str, str], int] = {}

    print(f"Engines: {', '.join(engines)}")

    label_set = _labels_label(labels_path)
    labels = parse_labels(labels_path, split_filter=split_filter)
    split_label = ",".join(sorted(split_filter)) if split_filter else "all"
    print(
        f"\n=== Label set: {label_set} [{split_label}] ===\n"
        f"Parsed {len(labels)} labeled files with {sum(len(f.measurements) for f in labels)} lines"
    )

    for engine_name in engines:
            print(f"\n=== Engine: {engine_name} ({label_set}) ===")
            try:
                engine = build_engine(engine_name)
            except Exception as exc:
                err = str(exc)
                print(f"  UNAVAILABLE: {err}")
                rows.append(
                    {
                        "label_set": label_set,
                        "labels_path": str(labels_path),
                        "engine": engine_name,
                        "mode": "raw_no_parser",
                        "status": "unavailable",
                        "error": err,
                    }
                )
                for parser_mode in parser_modes:
                    rows.append(
                        {
                            "label_set": label_set,
                            "labels_path": str(labels_path),
                            "engine": engine_name,
                            "mode": _parser_label(parser_mode),
                            "status": "unavailable",
                            "error": err,
                        }
                    )
                continue

            try:
                if not args.skip_raw:
                    raw_scores, raw_file_debug = run_raw_text_eval(labels, engine)
                    print(
                        "  raw_no_parser: "
                        f"text={format_rate(raw_scores.text_detect_rate)}, "
                        f"exact={format_rate(raw_scores.exact_hit_rate)}, "
                        f"value={format_rate(raw_scores.value_hit_rate)}"
                    )
                    rows.append(
                        {
                            "label_set": label_set,
                            "labels_path": str(labels_path),
                            "engine": engine_name,
                            "mode": "raw_no_parser",
                            "status": "ok",
                            "files": raw_scores.total_files,
                            "files_with_text": raw_scores.files_with_text,
                            "exact_match_rate": raw_scores.exact_hit_rate,
                            "value_match_rate": raw_scores.value_hit_rate,
                            "label_match_rate": raw_scores.label_hit_rate,
                            "prefix_match_rate": raw_scores.prefix_hit_rate,
                            "predictions": "",
                            "elapsed_s": raw_scores.elapsed_s,
                        }
                    )
                    for record in raw_file_debug:
                        record.label_set = label_set
                        record.labels_path = str(labels_path)
                        record.engine = engine_name
                        if args.save_roi_visualizations:
                            key = (label_set, engine_name, record.mode)
                            visuals = _save_roi_visualizations_for_record(
                                output_dir=output_dir,
                                root_dir=roi_visualization_root,
                                label_set=label_set,
                                engine_name=engine_name,
                                mode_name=record.mode,
                                file_record=_json_ready_file_debug_record(record),
                                limit=args.roi_visualization_limit,
                                counter_key=key,
                                counts=roi_visualization_counts,
                            )
                            record.roi_visualizations = visuals
                        detailed_rows.append(_json_ready_file_debug_record(record))

                for parser_mode in parser_modes:
                    parser_label = _parser_label(parser_mode)
                    parser_scores = run_evaluation(
                        labels,
                        engine,
                        verbose=False,
                        args=type("_Args", (), {"parser": parser_mode})(),
                    )
                    print(
                        f"  {parser_label}: "
                        f"text={format_rate(parser_scores['detection_rate'])}, "
                        f"exact={format_rate(parser_scores['full_match_rate'])}, "
                        f"value={format_rate(parser_scores['value_match_rate'])}"
                    )
                    rows.append(
                        {
                            "label_set": label_set,
                            "labels_path": str(labels_path),
                            "engine": engine_name,
                            "mode": parser_label,
                            "status": "ok",
                            "files": int(parser_scores["total_files"]),
                            "files_with_text": int(parser_scores["total_files_with_detections"]),
                            "exact_match_rate": parser_scores["full_match_rate"],
                            "value_match_rate": parser_scores["value_match_rate"],
                            "label_match_rate": parser_scores["label_match_rate"],
                            "prefix_match_rate": parser_scores["prefix_match_rate"],
                            "predictions": int(parser_scores["total_predicted"]),
                            "elapsed_s": parser_scores["elapsed_s"],
                        }
                    )

                    for file_detail in parser_scores.get("file_details", []):
                        expected_lines = [
                            _canonicalize_line(str(item.get("text", "")))
                            for item in file_detail.get("labels", [])
                            if str(item.get("text", "")).strip()
                        ]
                        predicted_lines = [
                            _prediction_to_line(prediction).line
                            for prediction in file_detail.get("frames", [{}])[0:0]
                        ]
                        predicted_lines = []
                        for frame in file_detail.get("frames", []):
                            for prediction in frame.get("predictions", []):
                                predicted_lines.append(_prediction_to_line(prediction).line)

                        mismatches = [
                            DetailedLineResult(
                                expected_line=match.get("expected_text", ""),
                                actual_line=match.get("predicted_text"),
                                exact_match=bool(match.get("full_match", False)),
                                prefix_match=bool(match.get("prefix_match", False)),
                                label_match=bool(match.get("label_match", False)),
                                value_match=bool(match.get("value_match", False)),
                                unit_match=bool(match.get("unit_match", False)),
                                error_type=_classify_mismatch(
                                    actual_present=match.get("predicted_text") is not None,
                                    exact_match=bool(match.get("full_match", False)),
                                    prefix_match=bool(match.get("prefix_match", False)),
                                    label_match=bool(match.get("label_match", False)),
                                    value_match=bool(match.get("value_match", False)),
                                    unit_match=bool(match.get("unit_match", False)),
                                ),
                            )
                            for match in file_detail.get("matches", [])
                            if not bool(match.get("full_match", False))
                        ]

                        record = FileDebugRecord(
                            label_set=label_set,
                            labels_path=str(labels_path),
                            engine=engine_name,
                            mode=parser_label,
                            file_path=str(file_detail.get("file_path", "")),
                            file_name=str(file_detail.get("file_name", "")),
                            total_labels=int(file_detail.get("total_labels", 0)),
                            exact_matches=int(file_detail.get("full_matches", 0)),
                            value_matches=int(file_detail.get("value_matches", 0)),
                            label_matches=int(file_detail.get("label_matches", 0)),
                            prefix_matches=int(file_detail.get("prefix_matches", 0)),
                            text_present=bool(file_detail.get("predicted_count", 0)),
                            roi_frames=[
                                FrameDebugInfo(
                                    frame_index=int(frame.get("frame_index", 0)),
                                    roi_present=frame.get("roi_bbox") is not None,
                                    roi_bbox=tuple(frame["roi_bbox"]) if frame.get("roi_bbox") is not None else None,
                                    ocr_bbox=tuple(frame["ocr_bbox"]) if frame.get("ocr_bbox") is not None else None,
                                    roi_confidence=float(frame.get("roi_confidence", 0.0)),
                                    raw_text=str(frame.get("raw_ocr_text", "")),
                                )
                                for frame in file_detail.get("frames", [])
                            ],
                            expected_lines=expected_lines,
                            predicted_lines=predicted_lines,
                            mismatches=mismatches,
                        )
                        if args.save_roi_visualizations:
                            key = (label_set, engine_name, parser_label)
                            visuals = _save_roi_visualizations_for_record(
                                output_dir=output_dir,
                                root_dir=roi_visualization_root,
                                label_set=label_set,
                                engine_name=engine_name,
                                mode_name=parser_label,
                                file_record=_json_ready_file_debug_record(record),
                                limit=args.roi_visualization_limit,
                                counter_key=key,
                                counts=roi_visualization_counts,
                            )
                            record.roi_visualizations = visuals
                        detailed_rows.append(_json_ready_file_debug_record(record))

            except Exception as exc:
                err = str(exc)
                print(f"  ERROR: {err}")
                rows.append(
                    {
                        "label_set": label_set,
                        "labels_path": str(labels_path),
                        "engine": engine_name,
                        "mode": "error",
                        "status": "error",
                        "error": err,
                    }
                )

    if args.local_llm_only:
        if not _ollama_is_healthy(args.ollama_url):
            raise SystemExit(f"Ollama is not reachable at {args.ollama_url}")
        model = _select_vision_model(args.local_llm_only_model, args.ollama_url)
        vision_mode = "local_vision_llm_only"
        print(f"\n=== Vision LLM: {model} ({label_set}) ===")
        vision_scores, vision_file_debug = run_local_vision_llm_eval(
            labels,
            model=model,
            ollama_url=args.ollama_url,
            timeout_s=args.local_llm_timeout,
        )
        print(
            f"  {vision_mode}: "
            f"text={format_rate(vision_scores['text_detect_rate'])}, "
            f"exact={format_rate(vision_scores['exact_match_rate'])}, "
            f"value={format_rate(vision_scores['value_match_rate'])}"
        )
        rows.append(
            {
                "label_set": label_set,
                "labels_path": str(labels_path),
                "engine": model,
                "mode": vision_mode,
                "status": "ok",
                "files": int(vision_scores["total_files"]),
                "files_with_text": int(vision_scores["total_files_with_text"]),
                "exact_match_rate": vision_scores["exact_match_rate"],
                "value_match_rate": vision_scores["value_match_rate"],
                "label_match_rate": vision_scores["label_match_rate"],
                "prefix_match_rate": vision_scores["prefix_match_rate"],
                "predictions": int(vision_scores["total_predicted"]),
                "elapsed_s": vision_scores["elapsed_s"],
            }
        )
        for record in vision_file_debug:
            record.label_set = label_set
            record.labels_path = str(labels_path)
            if args.save_roi_visualizations:
                key = (label_set, model, vision_mode)
                visuals = _save_roi_visualizations_for_record(
                    output_dir=output_dir,
                    root_dir=roi_visualization_root,
                    label_set=label_set,
                    engine_name=model,
                    mode_name=vision_mode,
                    file_record=_json_ready_file_debug_record(record),
                    limit=args.roi_visualization_limit,
                    counter_key=key,
                    counts=roi_visualization_counts,
                )
                record.roi_visualizations = visuals
            detailed_rows.append(_json_ready_file_debug_record(record))

    elapsed_all = time.perf_counter() - started_all

    csv_path = output_dir / "ocr_engine_matrix.csv"
    json_path = output_dir / "ocr_engine_matrix.json"
    md_path = output_dir / "ocr_engine_matrix.md"

    csv_fields = [
        "label_set",
        "labels_path",
        "engine",
        "mode",
        "status",
        "files",
        "files_with_text",
        "exact_match_rate",
        "value_match_rate",
        "label_match_rate",
        "prefix_match_rate",
        "predictions",
        "elapsed_s",
        "error",
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in csv_fields})

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at_s": elapsed_all,
                "rows": rows,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )

    md_lines: list[str] = [
        "# OCR Engine Comparison",
        "",
        "_All evaluations in this report use the strict measurement ROI detector and canonical exact-line JSON labels._",
        "",
        f"Total runtime: {elapsed_all:.1f}s",
        "",
    ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("label_set", "")), []).append(row)

    for label_set, items in grouped.items():
        md_lines.append(f"## Label Set: {label_set}")
        md_lines.append("")

        raw_rows = [row for row in items if row.get("mode") == "raw_no_parser" and row.get("status") == "ok"]
        if raw_rows:
            md_lines.extend(
                [
                    "### Raw OCR Text",
                    "",
                    "| Engine | Files | Files With Text | Exact Match | Value Match | Label Match | Prefix Match | Time (s) |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for row in raw_rows:
                md_lines.append(
                    "| "
                    f"{row['engine']} | {row['files']} | {row['files_with_text']} | "
                    f"{format_rate(float(row['exact_match_rate']))} | "
                    f"{format_rate(float(row['value_match_rate']))} | "
                    f"{format_rate(float(row['label_match_rate']))} | "
                    f"{format_rate(float(row['prefix_match_rate']))} | "
                    f"{float(row['elapsed_s']):.1f} |"
                )
            md_lines.append("")

        parser_rows = [
            row
            for row in items
            if row.get("mode") not in {"raw_no_parser", "error"} and row.get("status") == "ok"
        ]
        if parser_rows:
            md_lines.extend(
                [
                    "### Parsed Output",
                    "",
                    "| Engine | Mode | Files | Files With Text | Exact Match | Value Match | Label Match | Prefix Match | Predictions | Time (s) |",
                    "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for row in parser_rows:
                md_lines.append(
                    "| "
                    f"{row['engine']} | {row['mode']} | {row['files']} | {row['files_with_text']} | "
                    f"{format_rate(float(row['exact_match_rate']))} | "
                    f"{format_rate(float(row['value_match_rate']))} | "
                    f"{format_rate(float(row['label_match_rate']))} | "
                    f"{format_rate(float(row['prefix_match_rate']))} | "
                    f"{row['predictions']} | {float(row['elapsed_s']):.1f} |"
                )
            md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    saved_outputs = [csv_path, json_path, md_path]

    if args.write_detailed_report:
        detailed_json_path = output_dir / args.detailed_report_name
        with detailed_json_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "files": detailed_rows,
                    "elapsed_s": elapsed_all,
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )
        saved_outputs.append(detailed_json_path)

    if args.write_detailed_markdown:
        detailed_md_path = output_dir / args.detailed_markdown_name
        lines = [
            "# OCR Engine Detailed Per-File Report",
            "",
            "_This report is intended for exact-line academic error analysis._",
            "",
        ]
        grouped_details: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for row in detailed_rows:
            key = (
                str(row.get("label_set", "")),
                str(row.get("engine", "")),
                str(row.get("mode", "")),
            )
            grouped_details.setdefault(key, []).append(row)

        for (label_set, engine_name, mode_name), items in grouped_details.items():
            lines.append(f"## {label_set} / {engine_name} / {mode_name}")
            lines.append("")
            for item in items:
                lines.append(f"### {item.get('file_name', '')}")
                lines.append("")
                lines.append(f"- File: `{item.get('file_path', '')}`")
                lines.append(f"- Labels: {item.get('total_labels', 0)}")
                lines.append(f"- Exact matches: {item.get('exact_matches', 0)}")
                lines.append(f"- Value matches: {item.get('value_matches', 0)}")
                lines.append(f"- Label matches: {item.get('label_matches', 0)}")
                lines.append(f"- Prefix matches: {item.get('prefix_matches', 0)}")
                lines.append(f"- Text present: {item.get('text_present', False)}")
                lines.append("")
                lines.append("#### Expected lines")
                for expected in item.get("expected_lines", []):
                    lines.append(f"- `{expected}`")
                lines.append("")
                lines.append("#### Predicted lines")
                predictions = item.get("predicted_lines", [])
                if predictions:
                    for predicted in predictions:
                        lines.append(f"- `{predicted}`")
                else:
                    lines.append("- `NO PREDICTIONS`")
                lines.append("")
                lines.append("#### ROI frames")
                for frame in item.get("roi_frames", []):
                    lines.append(
                        "- "
                        f"frame={frame.get('frame_index')} "
                        f"present={frame.get('roi_present')} "
                        f"bbox={frame.get('roi_bbox')} "
                        f"ocr_bbox={frame.get('ocr_bbox')} "
                        f"confidence={frame.get('roi_confidence')}"
                    )
                lines.append("")
                if item.get("roi_visualizations"):
                    lines.append("#### ROI visualizations")
                    for image in item.get("roi_visualizations", []):
                        lines.append(f"- `{image}`")
                    lines.append("")
                lines.append("#### Mismatches")
                mismatches = item.get("mismatches", [])
                if mismatches:
                    for mismatch in mismatches:
                        lines.append(
                            f"- `{mismatch.get('error_type', 'unknown')}` | "
                            f"expected: `{mismatch.get('expected_line', '')}` | "
                            f"actual: `{mismatch.get('actual_line') or 'NOT FOUND'}`"
                        )
                else:
                    lines.append("- none")
                lines.append("")
        detailed_md_path.write_text("\n".join(lines), encoding="utf-8")
        saved_outputs.append(detailed_md_path)

    if args.write_html_report:
        detailed_html_path = output_dir / args.html_report_name
        detailed_html_path.write_text(
            _render_html_report(
                detailed_rows,
                title="OCR Engine Detailed Per-File Report",
            ),
            encoding="utf-8",
        )
        saved_outputs.append(detailed_html_path)

    print("\nSaved outputs:")
    for path in saved_outputs:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
