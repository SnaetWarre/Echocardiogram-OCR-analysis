from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.models.types import AiMeasurement
from app.pipeline.layout.line_segmenter import LineSegmenter, SegmentationResult
from app.pipeline.measurements.measurement_decoder import (
    canonicalize_exact_line,
    decode_lines_to_measurements,
    parse_measurement_line,
)
from app.pipeline.ocr.ocr_engines import OcrResult


def _empty_metadata() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class WholeBlobRecoveredLine:
    order: int
    text: str
    score: float
    source: str
    bbox: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class WholeBlobLineRecoveryResult:
    segmentation: SegmentationResult
    recovered_lines: tuple[WholeBlobRecoveredLine, ...] = field(default_factory=tuple)
    measurements: tuple[AiMeasurement, ...] = field(default_factory=tuple)
    raw_lines: tuple[str, ...] = field(default_factory=tuple)
    debug: dict[str, Any] = field(default_factory=_empty_metadata)


_TOKEN_RE = re.compile(r"\S+")
_INTEGER_TOKEN_RE = re.compile(r"^\d+$")
_UNITISH_TOKEN_RE = re.compile(r"^(%|mmhg|cm/s|m/s|cm|mm|ms|s|bpm|ml/m2|cm2|ml|m/s2)$", re.IGNORECASE)


def _clean_raw_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _canonical_line(text: str) -> str:
    return canonicalize_exact_line(str(text or "")).strip()


def _looks_like_label_start(token: str) -> bool:
    stripped = str(token or "").strip()
    if not stripped:
        return False
    if _UNITISH_TOKEN_RE.fullmatch(stripped):
        return False
    if _INTEGER_TOKEN_RE.fullmatch(stripped):
        return True
    return any(char.isalpha() for char in stripped)


def _split_single_blob_by_measurement_boundaries(tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return []

    recovered: list[str] = []
    start = 0
    for idx in range(1, len(tokens)):
        current_line = " ".join(tokens[start:idx]).strip()
        if not current_line:
            continue
        decoded = parse_measurement_line(current_line)
        next_token = tokens[idx]
        if not decoded.label or not decoded.value:
            continue
        if not _looks_like_label_start(next_token):
            continue
        if decoded.unit or _INTEGER_TOKEN_RE.fullmatch(next_token):
            recovered.append(_canonical_line(current_line))
            start = idx

    tail = _canonical_line(" ".join(tokens[start:]))
    if tail:
        recovered.append(tail)
    return [line for line in recovered if line]


def recover_lines_from_blob_text(
    text: str,
    *,
    target_line_count: int,
) -> tuple[list[str], dict[str, Any]]:
    raw_lines = _clean_raw_lines(text)
    canonical_raw_lines = [_canonical_line(line) for line in raw_lines if _canonical_line(line)]

    if target_line_count <= 0:
        return canonical_raw_lines, {
            "source": "raw_newlines",
            "target_line_count": int(target_line_count),
            "raw_line_count": len(canonical_raw_lines),
        }

    if len(canonical_raw_lines) == target_line_count and canonical_raw_lines:
        return canonical_raw_lines, {
            "source": "raw_newlines",
            "target_line_count": target_line_count,
            "raw_line_count": len(canonical_raw_lines),
        }

    # If the OCR engine already emitted multiple explicit lines, preserve them.
    # Projection-based row counts can over-segment due to empty top/header space, and
    # re-partitioning a good multi-line OCR result back into tokens can collapse
    # otherwise-correct lines into a single measurement string.
    if len(canonical_raw_lines) >= 2:
        return canonical_raw_lines, {
            "source": "raw_newlines_relaxed",
            "target_line_count": target_line_count,
            "raw_line_count": len(canonical_raw_lines),
        }

    tokens: list[str] = []
    newline_after_token_indexes: set[int] = set()
    for raw_line in raw_lines or [str(text or "")]:
        line_tokens = _TOKEN_RE.findall(raw_line)
        if not line_tokens:
            continue
        start_idx = len(tokens)
        tokens.extend(line_tokens)
        newline_after_token_indexes.add(start_idx + len(line_tokens) - 1)

    heuristic_lines = _split_single_blob_by_measurement_boundaries(tokens)
    if 1 < len(heuristic_lines) <= max(target_line_count, len(heuristic_lines)):
        return heuristic_lines, {
            "source": "unit_boundary_split",
            "target_line_count": target_line_count,
            "raw_line_count": len(canonical_raw_lines),
            "token_count": len(tokens),
        }

    if len(tokens) < target_line_count or not tokens:
        fallback_lines = canonical_raw_lines or [_canonical_line(text)] if str(text or "").strip() else []
        return fallback_lines, {
            "source": "fallback_raw_text",
            "target_line_count": target_line_count,
            "raw_line_count": len(canonical_raw_lines),
            "token_count": len(tokens),
        }

    min_tokens_per_line = 1

    def span_score(start: int, end: int, *, expected_tokens_per_line: float, max_tokens_per_line: int) -> float:
        span_tokens = tokens[start:end]
        candidate_text = " ".join(span_tokens).strip()
        if not candidate_text:
            return float("-inf")

        decoded = parse_measurement_line(candidate_text)
        canonical = decoded.canonical_text.strip()
        if not canonical:
            return float("-inf")

        score = float(decoded.syntax_confidence) * 12.0
        if decoded.label:
            score += 2.5
        else:
            score -= 2.5
        if decoded.value:
            score += 3.0
        else:
            score -= 2.5
        if decoded.unit:
            score += 1.0
        if decoded.prefix:
            score += 0.75

        token_count = end - start
        score -= 0.45 * abs(token_count - expected_tokens_per_line)
        if token_count > max_tokens_per_line:
            score -= 2.0 * (token_count - max_tokens_per_line)
        if token_count < min_tokens_per_line:
            score -= 4.0

        internal_prefix_count = sum(1 for token in span_tokens[1:] if _INTEGER_TOKEN_RE.fullmatch(token))
        if internal_prefix_count:
            score -= 2.25 * internal_prefix_count

        if any(char.isalpha() for char in canonical):
            score += 0.5
        else:
            score -= 3.0
        if any(char.isdigit() for char in canonical):
            score += 0.5
        else:
            score -= 1.5

        if end - 1 in newline_after_token_indexes:
            score += 1.2
        if start == 0 or (start - 1) in newline_after_token_indexes:
            score += 0.4

        return score

    def recover_exact_line_count(
        line_count: int,
    ) -> tuple[list[str] | None, dict[str, Any]]:
        if line_count <= 0 or len(tokens) < line_count:
            return None, {
                "line_count": line_count,
                "dp_failed": True,
            }

        expected_tokens_per_line = max(1.0, len(tokens) / float(line_count))
        max_tokens_per_line = max(4, int(round(expected_tokens_per_line * 2.5)))

        inf = float("-inf")
        dp = [[inf] * (len(tokens) + 1) for _ in range(line_count + 1)]
        prev = [[-1] * (len(tokens) + 1) for _ in range(line_count + 1)]
        dp[0][0] = 0.0

        for line_idx in range(1, line_count + 1):
            min_end = line_idx
            max_end = len(tokens) - (line_count - line_idx)
            for end in range(min_end, max_end + 1):
                best_score = inf
                best_start = -1
                start_floor = max(line_idx - 1, end - max_tokens_per_line)
                start_ceiling = end - min_tokens_per_line
                for start in range(start_floor, start_ceiling + 1):
                    prior = dp[line_idx - 1][start]
                    if prior == inf:
                        continue
                    candidate_score = prior + span_score(
                        start,
                        end,
                        expected_tokens_per_line=expected_tokens_per_line,
                        max_tokens_per_line=max_tokens_per_line,
                    )
                    if candidate_score > best_score:
                        best_score = candidate_score
                        best_start = start
                dp[line_idx][end] = best_score
                prev[line_idx][end] = best_start

        if prev[line_count][len(tokens)] < 0:
            return None, {
                "line_count": line_count,
                "dp_failed": True,
            }

        ranges: list[tuple[int, int]] = []
        end = len(tokens)
        for line_idx in range(line_count, 0, -1):
            start = prev[line_idx][end]
            if start < 0:
                return None, {
                    "line_count": line_count,
                    "dp_failed": True,
                }
            ranges.append((start, end))
            end = start
        ranges.reverse()

        recovered_lines = [
            _canonical_line(" ".join(tokens[start:end]))
            for start, end in ranges
        ]

        total_score = float(dp[line_count][len(tokens)])
        average_score = total_score / float(max(line_count, 1))
        return recovered_lines, {
            "line_count": line_count,
            "total_score": total_score,
            "average_score": average_score,
            "ranges": ranges,
        }

    best_lines: list[str] | None = None
    best_debug: dict[str, Any] | None = None
    best_selection_score = float("-inf")

    full_text_decoded = parse_measurement_line(" ".join(tokens))
    full_text_internal_prefix_count = sum(1 for token in tokens[1:] if _INTEGER_TOKEN_RE.fullmatch(token))

    for candidate_count in range(1, min(target_line_count, len(tokens)) + 1):
        candidate_lines, candidate_debug = recover_exact_line_count(candidate_count)
        if candidate_lines is None:
            continue

        selection_score = float(candidate_debug["average_score"])
        if len(canonical_raw_lines) > 1 and candidate_count == len(canonical_raw_lines):
            selection_score += 0.8
        if (
            candidate_count == 1
            and full_text_decoded.label
            and full_text_decoded.value
            and full_text_internal_prefix_count == 0
        ):
            selection_score += 3.0

        if selection_score > best_selection_score:
            best_selection_score = selection_score
            best_lines = candidate_lines
            best_debug = {
                **candidate_debug,
                "selection_score": selection_score,
            }

    if best_lines is None or best_debug is None:
        fallback_lines = canonical_raw_lines or [_canonical_line(text)] if str(text or "").strip() else []
        return fallback_lines, {
            "source": "fallback_raw_text",
            "target_line_count": target_line_count,
            "raw_line_count": len(canonical_raw_lines),
            "token_count": len(tokens),
            "dp_failed": True,
        }

    return best_lines, {
        "source": "dp_token_segmentation",
        "target_line_count": target_line_count,
        "selected_line_count": int(best_debug["line_count"]),
        "raw_line_count": len(canonical_raw_lines),
        "token_count": len(tokens),
        "ranges": best_debug["ranges"],
        "total_score": best_debug["total_score"],
        "average_score": best_debug["average_score"],
        "selection_score": best_debug["selection_score"],
    }


def recover_lines_from_whole_blob_ocr(
    roi: np.ndarray,
    ocr_result: OcrResult,
    *,
    segmenter: LineSegmenter | None = None,
    confidence: float | None = None,
) -> WholeBlobLineRecoveryResult:
    line_segmenter = segmenter or LineSegmenter()
    segmentation = line_segmenter.segment(roi, tokens=ocr_result.tokens)
    target_line_count = len(segmentation.lines)

    recovered_texts, debug = recover_lines_from_blob_text(
        ocr_result.text,
        target_line_count=target_line_count,
    )

    if not recovered_texts:
        recovered_texts = [_canonical_line(line) for line in _clean_raw_lines(ocr_result.text)]

    measurements = tuple(
        decode_lines_to_measurements(
            [line for line in recovered_texts if line.strip()],
            confidence=float(confidence if confidence is not None else ocr_result.confidence),
        )
    )

    recovered_lines: list[WholeBlobRecoveredLine] = []
    for order, line_text in enumerate(recovered_texts):
        bbox = segmentation.lines[order].bbox if order < len(segmentation.lines) else None
        recovered_lines.append(
            WholeBlobRecoveredLine(
                order=order,
                text=line_text,
                score=1.0,
                source=str(debug.get("source") or "unknown"),
                bbox=bbox,
            )
        )

    return WholeBlobLineRecoveryResult(
        segmentation=segmentation,
        recovered_lines=tuple(recovered_lines),
        measurements=measurements,
        raw_lines=tuple(_clean_raw_lines(ocr_result.text)),
        debug=dict(debug),
    )
