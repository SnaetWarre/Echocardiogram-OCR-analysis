from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.types import PipelineRequest
from app.ocr.preprocessing import _to_gray
from app.pipeline.ai_pipeline import PipelineConfig
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline
from app.pipeline.ocr_engines import build_engine
from app.validation.datasets import (
    LabeledFile,
    normalize_split_name,
    parse_labels,
    parse_requested_splits,
)
from app.validation.evaluation import score_predictions

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "ocr_redesign" / "preprocess_sweep"
DEFAULT_LABELS_PATH = PROJECT_ROOT / "labels" / "labels.json"


class PerFileTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class PreprocessSpec:
    contrast_mode: str = "none"
    scale_factor: int = 1
    scale_algo: str = "linear"
    unsharp: bool = False
    threshold_mode: str = "none"
    morph_close: bool = False
    smooth: bool = False
    input_mode: str = "gray"
    preprocess_order: str = "scale_then_threshold"
    binary_scale_algo: str = "nearest"


@dataclass(frozen=True)
class SweepConfig:
    name: str
    description: str
    default_view: PreprocessSpec
    multiview_mode: str = "none"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def _path_matches_glob(filename: str, pattern: str) -> bool:
    if fnmatch.fnmatch(filename, pattern):
        return True
    return fnmatch.fnmatch(filename.lower(), pattern.lower())


def _discover_files(root: Path, pattern: str, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if _path_matches_glob(root.name, pattern) else []
    if recursive:
        candidates = (p for p in root.rglob("*") if p.is_file())
    else:
        candidates = (p for p in root.iterdir() if p.is_file())
    files = [p for p in candidates if _path_matches_glob(p.name, pattern)]
    return sorted(files, key=lambda p: _canonical_path(p))


def _interpolation_flag(algo: str) -> int:
    interpolation_map = {
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "lanczos": cv2.INTER_LANCZOS4,
        "nearest": cv2.INTER_NEAREST,
    }
    return interpolation_map.get(str(algo).lower(), cv2.INTER_CUBIC)


def _ensure_initial_working(image: np.ndarray, input_mode: str) -> np.ndarray:
    mode = str(input_mode or "gray").lower()
    if image.size == 0:
        return image
    if mode == "bgr":
        if image.ndim == 2:
            return cv2.cvtColor(image.astype(np.uint8, copy=False), cv2.COLOR_GRAY2BGR)
        if image.ndim == 3 and image.shape[-1] >= 3:
            return image[..., :3].astype(np.uint8, copy=False)
        raise ValueError(f"bgr input_mode requires 2d or 3d image, got shape {image.shape}")
    return _to_gray(image)


def _to_gray_plane_if_needed(working: np.ndarray) -> np.ndarray:
    if working.ndim == 3:
        return _to_gray(working)
    return working


def _apply_contrast(working: np.ndarray, spec: PreprocessSpec) -> np.ndarray:
    if spec.contrast_mode == "none":
        return working
    base = _to_gray_plane_if_needed(working)
    if spec.contrast_mode == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(base)
    if spec.contrast_mode == "adaptive_threshold":
        return cv2.equalizeHist(base)
    return base


def _apply_unsharp(working: np.ndarray, spec: PreprocessSpec) -> np.ndarray:
    if not spec.unsharp:
        return working
    gaussian = cv2.GaussianBlur(working, (5, 5), 1.0)
    return cv2.addWeighted(working, 1.5, gaussian, -0.5, 0)


def _apply_resize(working: np.ndarray, scale: int, algo: str) -> np.ndarray:
    if scale <= 1:
        return working
    inter_flag = _interpolation_flag(algo)
    width = int(working.shape[1] * scale)
    height = int(working.shape[0] * scale)
    return cv2.resize(working, (width, height), interpolation=inter_flag)


def _apply_threshold_morph_smooth(working: np.ndarray, spec: PreprocessSpec) -> np.ndarray:
    if spec.threshold_mode == "none":
        return working
    gray = _to_gray_plane_if_needed(working)
    if spec.threshold_mode == "adaptive":
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
    elif spec.threshold_mode == "otsu":
        _ret, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        return working

    out = binary
    if spec.morph_close:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, kernel)

    if spec.smooth:
        blurred = cv2.GaussianBlur(out, (3, 3), 0.6)
        _ret, out = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

    return out


def _preprocess_with_spec(image: np.ndarray, spec: PreprocessSpec) -> np.ndarray:
    working = _ensure_initial_working(image, spec.input_mode)
    if working.size == 0:
        return working

    working = _apply_contrast(working, spec)
    working = _apply_unsharp(working, spec)

    scale = max(1, min(int(spec.scale_factor), 6))
    order = str(spec.preprocess_order or "scale_then_threshold").lower()
    if order not in ("scale_then_threshold", "threshold_then_scale"):
        order = "scale_then_threshold"

    if spec.threshold_mode == "none":
        return _apply_resize(working, scale, spec.scale_algo)

    if order == "scale_then_threshold":
        working = _apply_resize(working, scale, spec.scale_algo)
        return _apply_threshold_morph_smooth(working, spec)

    working = _apply_threshold_morph_smooth(working, spec)
    return _apply_resize(working, scale, spec.binary_scale_algo)


def preprocess_spec_from_dict(data: dict[str, Any]) -> PreprocessSpec:
    allowed = {f.name for f in fields(PreprocessSpec)}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    return PreprocessSpec(**kwargs)


def _pipeline_alt_views(default_spec: PreprocessSpec) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    high_contrast = PreprocessSpec(
        contrast_mode="adaptive_threshold",
        scale_factor=default_spec.scale_factor,
        scale_algo=default_spec.scale_algo,
        unsharp=default_spec.unsharp,
        threshold_mode="adaptive",
        morph_close=True,
        smooth=False,
        input_mode=default_spec.input_mode,
        preprocess_order=default_spec.preprocess_order,
        binary_scale_algo=default_spec.binary_scale_algo,
    )
    clahe = PreprocessSpec(
        contrast_mode="clahe",
        scale_factor=default_spec.scale_factor,
        scale_algo=default_spec.scale_algo,
        unsharp=default_spec.unsharp,
        threshold_mode="otsu",
        morph_close=True,
        smooth=False,
        input_mode=default_spec.input_mode,
        preprocess_order=default_spec.preprocess_order,
        binary_scale_algo=default_spec.binary_scale_algo,
    )
    return {
        "high_contrast": lambda image, _spec=high_contrast: _preprocess_with_spec(image, _spec),
        "clahe": lambda image, _spec=clahe: _preprocess_with_spec(image, _spec),
    }


def _build_preprocess_views(config: SweepConfig) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    views: dict[str, Callable[[np.ndarray], np.ndarray]] = {
        "default": lambda image, _spec=config.default_view: _preprocess_with_spec(image, _spec)
    }
    if config.multiview_mode == "pipeline":
        views.update(_pipeline_alt_views(config.default_view))
    return views


def _smoke_configs() -> list[SweepConfig]:
    return [
        SweepConfig(
            name="no_preprocess_gray",
            description="Grayscale only, no upscale, no sharpening, no binarization, no multiview.",
            default_view=PreprocessSpec(),
        ),
        SweepConfig(
            name="default_single",
            description="Current step-6 style default only: unsharp, x3 Lanczos, Otsu, morph close.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_multiview",
            description="Current step-6 plus step-7 multiview retries (adaptive + clahe).",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
            multiview_mode="pipeline",
        ),
    ]


def _broad_configs() -> list[SweepConfig]:
    return [
        SweepConfig(
            name="no_preprocess_gray",
            description="Grayscale only, no upscale, no sharpening, no binarization, no multiview.",
            default_view=PreprocessSpec(),
        ),
        SweepConfig(
            name="gray_x2_cubic",
            description="Grayscale only with x2 cubic upscale.",
            default_view=PreprocessSpec(scale_factor=2, scale_algo="cubic"),
        ),
        SweepConfig(
            name="gray_x3_lanczos",
            description="Grayscale only with x3 Lanczos upscale.",
            default_view=PreprocessSpec(scale_factor=3, scale_algo="lanczos"),
        ),
        SweepConfig(
            name="unsharp_x3_lanczos",
            description="Grayscale + unsharp mask + x3 Lanczos, no binarization.",
            default_view=PreprocessSpec(scale_factor=3, scale_algo="lanczos", unsharp=True),
        ),
        SweepConfig(
            name="otsu_x3_lanczos_no_unsharp",
            description="Grayscale + x3 Lanczos + Otsu threshold, no unsharp, no morph close.",
            default_view=PreprocessSpec(
                scale_factor=3,
                scale_algo="lanczos",
                threshold_mode="otsu",
            ),
        ),
        SweepConfig(
            name="otsu_close_x3_lanczos_no_unsharp",
            description="Grayscale + x3 Lanczos + Otsu + morph close, no unsharp.",
            default_view=PreprocessSpec(
                scale_factor=3,
                scale_algo="lanczos",
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_single",
            description="Current step-6 style default only: unsharp, x3 Lanczos, Otsu, morph close.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_multiview",
            description="Current step-6 plus step-7 multiview retries (adaptive + clahe).",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
            multiview_mode="pipeline",
        ),
        SweepConfig(
            name="default_smooth_single",
            description="Current step-6 default with extra post-binary smoothing.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
                smooth=True,
            ),
        ),
        SweepConfig(
            name="default_x2_lanczos_single",
            description="Current default pipeline but x2 Lanczos instead of x3.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=2,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_x3_cubic_single",
            description="Current default pipeline but x3 cubic instead of Lanczos.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="cubic",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="default_x3_linear_single",
            description="Current default pipeline but x3 linear instead of Lanczos.",
            default_view=PreprocessSpec(
                contrast_mode="none",
                scale_factor=3,
                scale_algo="linear",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="clahe_single",
            description="CLAHE + unsharp + x3 Lanczos + Otsu + morph close, no multiview.",
            default_view=PreprocessSpec(
                contrast_mode="clahe",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="otsu",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="adaptive_single",
            description="Equalize hist + unsharp + x3 Lanczos + adaptive threshold + morph close.",
            default_view=PreprocessSpec(
                contrast_mode="adaptive_threshold",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="adaptive",
                morph_close=True,
            ),
        ),
        SweepConfig(
            name="adaptive_smooth_single",
            description="Adaptive-threshold pipeline with extra post-binary smoothing.",
            default_view=PreprocessSpec(
                contrast_mode="adaptive_threshold",
                scale_factor=3,
                scale_algo="lanczos",
                unsharp=True,
                threshold_mode="adaptive",
                morph_close=True,
                smooth=True,
            ),
        ),
    ]


def _parse_csv_ints(text: str) -> list[int]:
    return [int(item.strip()) for item in text.split(",") if item.strip()]


def _parse_csv_lower(text: str) -> list[str]:
    return [item.strip().lower() for item in text.split(",") if item.strip()]


def _normalize_preprocess_order_token(token: str) -> str | None:
    t = token.strip().lower().replace("-", "_")
    aliases_st = {"scale_then_threshold", "scale_first", "st", "sf"}
    aliases_ts = {"threshold_then_scale", "bin_first", "threshold_first", "ts", "bf"}
    if t in aliases_st:
        return "scale_then_threshold"
    if t in aliases_ts:
        return "threshold_then_scale"
    return None


def _build_order_matrix_configs(args: Any) -> list[SweepConfig]:
    scales = _parse_csv_ints(args.matrix_scales)
    bins = _parse_csv_lower(args.matrix_bin)
    order_tokens = [x.strip() for x in str(args.matrix_order).split(",") if x.strip()]
    recipes = _parse_csv_lower(args.matrix_recipe)
    inmodes = _parse_csv_lower(args.matrix_input)
    scale_algo = str(args.matrix_scale_algo or "lanczos").strip() or "lanczos"
    binary_scale_algo = str(args.matrix_binary_scale_algo or "nearest").strip() or "nearest"
    multiview_raw = str(getattr(args, "matrix_multiview", "none") or "none")
    multiview_modes: list[str] = []
    for part in multiview_raw.split(","):
        mv = part.strip().lower()
        if mv in ("none", "pipeline") and mv not in multiview_modes:
            multiview_modes.append(mv)
    if not multiview_modes:
        multiview_modes = ["none"]

    order_choices: list[str] = []
    for tok in order_tokens:
        norm = _normalize_preprocess_order_token(tok)
        if norm and norm not in order_choices:
            order_choices.append(norm)
    if not order_choices:
        order_choices = ["scale_then_threshold", "threshold_then_scale"]

    configs: list[SweepConfig] = []
    for multiview in multiview_modes:
        for im in inmodes:
            if im not in ("gray", "bgr"):
                continue
            for recipe in recipes:
                if recipe in ("plain", "pln", "p"):
                    unsharp = False
                elif recipe in ("unsharp", "ush", "u"):
                    unsharp = True
                else:
                    continue
                for scale in scales:
                    if scale < 1 or scale > 6:
                        continue
                    for bin_mode in bins:
                        if bin_mode in ("none", "off", "nbin", "no"):
                            threshold_mode = "none"
                        elif bin_mode in ("otsu", "bin"):
                            threshold_mode = "otsu"
                        else:
                            continue

                        morph_close = bool(
                            threshold_mode == "otsu"
                            and not getattr(args, "matrix_no_morph_close", False)
                        )

                        if threshold_mode == "otsu" and int(scale) == 1 and not getattr(
                            args, "matrix_include_bin_1x", False
                        ):
                            continue

                        if threshold_mode == "none":
                            order_iter = ["scale_then_threshold"]
                        else:
                            order_iter = list(order_choices)

                        for ordv in order_iter:
                            im_short = "bgr" if im == "bgr" else "gray"
                            rec_short = "ush" if unsharp else "pln"
                            bin_short = "nbin" if threshold_mode == "none" else "otsu"
                            ord_short = "st" if ordv == "scale_then_threshold" else "ts"
                            mc_short = ""
                            if threshold_mode != "none":
                                mc_short = "_nm" if not morph_close else "_mc"
                            mv_short = "mv0" if multiview == "none" else "mv1"
                            name = f"om_{im_short}_{rec_short}_s{scale}_{bin_short}_{ord_short}{mc_short}_{mv_short}"
                            desc = (
                                f"order_matrix: input={im_short}, "
                                f"recipe={'unsharp' if unsharp else 'plain'}, "
                                f"scale={scale}x {scale_algo}, bin={bin_short}, order={ordv}, "
                                f"morph_close={morph_close}, multiview={multiview}"
                            )
                            spec = PreprocessSpec(
                                contrast_mode="none",
                                scale_factor=int(scale),
                                scale_algo=scale_algo,
                                unsharp=unsharp,
                                threshold_mode=threshold_mode,
                                morph_close=morph_close,
                                smooth=False,
                                input_mode=im,
                                preprocess_order=ordv,
                                binary_scale_algo=binary_scale_algo,
                            )
                            configs.append(
                                SweepConfig(
                                    name=name,
                                    description=desc,
                                    default_view=spec,
                                    multiview_mode=multiview,
                                )
                            )
    return configs


def _order_matrix_plan_configs() -> list[SweepConfig]:
    """Eight fixed rows: bin/up ablation + Lanczos vs cubic for every 3× path.

    Names read as: ``plan_<pipeline>_<scale>_<interp?>`` — e.g. ``plan_no_binarize_3x_lanczos``,
    ``plan_scale_then_otsu_3x_cubic`` (upscale *then* Otsu), ``plan_otsu_then_scale_3x_lanczos``
    (Otsu on 1× crop, then ``nearest`` binary upscale). Baseline rows end in ``_1x``.

    Gray, plain, multiview off. Full factorial: ``order_matrix`` / ``run_full_preprocess_sweep.sh``.
    """
    binary_scale_algo = "nearest"
    rows: list[SweepConfig] = []

    def push(
        *,
        name: str,
        description: str,
        scale_factor: int,
        threshold_mode: str,
        preprocess_order: str,
        scale_algo: str,
    ) -> None:
        morph = threshold_mode == "otsu"
        rows.append(
            SweepConfig(
                name=name,
                description=description,
                default_view=PreprocessSpec(
                    contrast_mode="none",
                    scale_factor=int(scale_factor),
                    scale_algo=scale_algo,
                    unsharp=False,
                    threshold_mode=threshold_mode,
                    morph_close=morph,
                    smooth=False,
                    input_mode="gray",
                    preprocess_order=preprocess_order,
                    binary_scale_algo=binary_scale_algo,
                ),
                multiview_mode="none",
            )
        )

    push(
        name="plan_no_binarize_1x",
        description="no bin, no upscale (1×)",
        scale_factor=1,
        threshold_mode="none",
        preprocess_order="scale_then_threshold",
        scale_algo="lanczos",
    )
    push(
        name="plan_no_binarize_3x_lanczos",
        description="no bin, 3× Lanczos",
        scale_factor=3,
        threshold_mode="none",
        preprocess_order="scale_then_threshold",
        scale_algo="lanczos",
    )
    push(
        name="plan_no_binarize_3x_cubic",
        description="no bin, 3× cubic",
        scale_factor=3,
        threshold_mode="none",
        preprocess_order="scale_then_threshold",
        scale_algo="cubic",
    )
    push(
        name="plan_scale_then_otsu_1x",
        description="Otsu at 1× (no upscale; scale_then_threshold)",
        scale_factor=1,
        threshold_mode="otsu",
        preprocess_order="scale_then_threshold",
        scale_algo="lanczos",
    )
    push(
        name="plan_scale_then_otsu_3x_lanczos",
        description="3× Lanczos then Otsu (scale_then_threshold)",
        scale_factor=3,
        threshold_mode="otsu",
        preprocess_order="scale_then_threshold",
        scale_algo="lanczos",
    )
    push(
        name="plan_scale_then_otsu_3x_cubic",
        description="3× cubic then Otsu (scale_then_threshold)",
        scale_factor=3,
        threshold_mode="otsu",
        preprocess_order="scale_then_threshold",
        scale_algo="cubic",
    )
    push(
        name="plan_otsu_then_scale_3x_lanczos",
        description="Otsu then 3× Lanczos (threshold_then_scale; nearest on binary)",
        scale_factor=3,
        threshold_mode="otsu",
        preprocess_order="threshold_then_scale",
        scale_algo="lanczos",
    )
    push(
        name="plan_otsu_then_scale_3x_cubic",
        description="Otsu then 3× cubic (threshold_then_scale; nearest on binary)",
        scale_factor=3,
        threshold_mode="otsu",
        preprocess_order="threshold_then_scale",
        scale_algo="cubic",
    )
    return rows


def _load_manifest_configs(path: Path) -> list[SweepConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "configs" in raw:
        raw = raw["configs"]
    if not isinstance(raw, list):
        raise ValueError(f"Manifest {path} must be a JSON array (or an object with a 'configs' array).")
    out: list[SweepConfig] = []
    for idx, obj in enumerate(raw):
        if not isinstance(obj, dict):
            raise ValueError(f"Manifest entry {idx} must be a JSON object.")
        name = str(obj.get("name") or f"manifest_{idx}").strip() or f"manifest_{idx}"
        desc = str(obj.get("description") or "")
        mv = str(obj.get("multiview_mode") or "none").strip()
        if mv not in ("none", "pipeline"):
            mv = "none"
        dv = obj.get("default_view")
        if not isinstance(dv, dict):
            dv = {}
        out.append(
            SweepConfig(
                name=name,
                description=desc,
                default_view=preprocess_spec_from_dict(dv),
                multiview_mode=mv,
            )
        )
    return out


def _restrict_discovered_paths(
    discovered: list[Path],
    *,
    label_scores_path: Path | None,
    paths_file: Path | None,
    split_filter: set[str],
) -> list[Path]:
    restricts: list[set[str]] = []
    if paths_file is not None:
        p = paths_file.expanduser().resolve()
        if p.is_file():
            keys: set[str] = set()
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                keys.add(_canonical_path(Path(line)))
            restricts.append(keys)
    if label_scores_path is not None:
        p = label_scores_path.expanduser().resolve()
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            keys = set()
            details = data.get("file_details", [])
            if not isinstance(details, list):
                details = []
            for fd in details:
                if not isinstance(fd, dict):
                    continue
                split_name = normalize_split_name(str(fd.get("split") or ""))
                if split_filter and split_name not in split_filter:
                    continue
                matches = fd.get("matches") or []
                if not isinstance(matches, list):
                    matches = []
                has_failure = any(
                    not bool(m.get("full_match", True)) for m in matches if isinstance(m, dict)
                )
                if not has_failure:
                    continue
                fp = str(fd.get("file_path") or "").strip()
                if fp:
                    keys.add(_canonical_path(Path(fp)))
            restricts.append(keys)

    if not restricts:
        return discovered
    allow = set.intersection(*restricts) if len(restricts) > 1 else restricts[0]
    out = [path for path in discovered if _canonical_path(path) in allow]
    return sorted(out, key=lambda p: _canonical_path(p))


def _select_configs(config_set: str) -> list[SweepConfig]:
    if config_set == "smoke":
        return _smoke_configs()
    if config_set == "broad":
        return _broad_configs()
    raise ValueError(f"Unsupported config set: {config_set}")


def _filter_configs(
    configs: list[SweepConfig],
    *,
    only_configs: str,
    exclude_configs: str,
) -> list[SweepConfig]:
    selected = configs
    if only_configs.strip():
        wanted = {item.strip() for item in only_configs.split(",") if item.strip()}
        selected = [config for config in selected if config.name in wanted]
    if exclude_configs.strip():
        blocked = {item.strip() for item in exclude_configs.split(",") if item.strip()}
        selected = [config for config in selected if config.name not in blocked]
    return selected


def _build_pipeline(engine_name: str, parser_mode: str, config: SweepConfig) -> EchoOcrPipeline:
    engine = build_engine(engine_name)
    pipeline = EchoOcrPipeline(
        ocr_engine=engine,
        config=PipelineConfig(
            parameters={
                "ocr_engine": engine_name,
                "requested_ocr_engine": engine_name,
                "parser_mode": parser_mode,
            }
        ),
    )
    pipeline._line_transcriber.preprocess_views = _build_preprocess_views(config)
    pipeline.ensure_components()
    return pipeline


def _result_to_item(path: Path, result: Any, config: SweepConfig) -> dict[str, Any]:
    if getattr(result, "status", "") != "ok" or getattr(result, "ai_result", None) is None:
        return {
            "dicom_path": _canonical_path(path),
            "status": "error",
            "measurements": [],
            "line_predictions": [],
            "metadata": {"config_name": config.name},
            "error": str(getattr(result, "error", "unknown error")),
        }

    ai_result = result.ai_result
    raw = ai_result.raw if isinstance(ai_result.raw, dict) else {}
    measurements = [
        {
            "name": measurement.name,
            "value": measurement.value,
            "unit": measurement.unit,
            "source": measurement.source,
        }
        for measurement in ai_result.measurements
    ]
    line_predictions = []
    for entry in raw.get("line_predictions", []) if isinstance(raw.get("line_predictions", []), list) else []:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        line_predictions.append(
            {
                "order": entry.get("order"),
                "text": text,
                "confidence": entry.get("confidence"),
                "parser_source": entry.get("parser_source"),
            }
        )
    return {
        "dicom_path": _canonical_path(path),
        "status": "ok",
        "measurements": measurements,
        "line_predictions": line_predictions,
        "metadata": {
            "config_name": config.name,
            "model_name": ai_result.model_name,
            "record_count": raw.get("record_count", 0),
            "line_prediction_count": len(raw.get("line_predictions", []))
            if isinstance(raw.get("line_predictions", []), list)
            else 0,
            "parser_sources": raw.get("parser_sources", []),
            "source_kinds": raw.get("source_kinds", []),
        },
        "error": None,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _checkpoint_path_for(config_dir: Path) -> Path:
    return config_dir / "checkpoint.json"


def _load_checkpoint(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.exists():
        return [], {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    manifest = payload.get("manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    return [item for item in items if isinstance(item, dict)], manifest


def _write_checkpoint(
    path: Path,
    *,
    config: SweepConfig,
    items: list[dict[str, Any]],
    engine: str,
    parser_mode: str,
    input_path: Path,
    started_at: str,
    elapsed_s: float,
    ok_files: int,
    error_files: int,
) -> None:
    payload = {
        "manifest": {
            "run_type": "preprocess_sweep_checkpoint",
            "config_name": config.name,
            "config": asdict(config),
            "engine": engine,
            "parser_mode": parser_mode,
            "input_path": _canonical_path(input_path),
            "started_at": started_at,
            "elapsed_s": round(elapsed_s, 3),
            "processed_files": len(items),
            "ok_files": ok_files,
            "error_files": error_files,
            "updated_at": _iso_now(),
            "pid": os.getpid(),
        },
        "items": items,
    }
    _write_json(path, payload)


def _clean_checkpoint(path: Path) -> None:
    if path.exists():
        path.unlink()


def _result_error_item(path: Path, config: SweepConfig, error_type: str, message: str) -> dict[str, Any]:
    return {
        "dicom_path": _canonical_path(path),
        "status": "error",
        "measurements": [],
        "line_predictions": [],
        "metadata": {"config_name": config.name},
        "error": {"type": error_type, "message": message},
    }


def _alarm_handler(_signum: int, _frame: Any) -> None:
    raise PerFileTimeoutError("Per-DICOM timeout reached.")


def _run_with_timeout(timeout_s: int, func: Callable[[], Any]) -> Any:
    if timeout_s <= 0:
        return func()
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0.0)
    try:
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
        return func()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _dispose_engine(engine: Any) -> None:
    stop = getattr(engine, "_stop_worker", None)
    if callable(stop):
        try:
            stop()
        except Exception:
            pass
    primary = getattr(engine, "primary", None)
    if primary is not None:
        _dispose_engine(primary)
    fallback = getattr(engine, "fallback", None)
    if fallback is not None:
        _dispose_engine(fallback)


def _dispose_pipeline(pipeline: EchoOcrPipeline | None) -> None:
    if pipeline is None:
        return
    _dispose_engine(getattr(pipeline, "ocr_engine", None))
    _dispose_engine(getattr(pipeline, "_fallback_ocr_engine", None))


def _score_labeled_subset(
    items: list[dict[str, Any]],
    labeled_files: list[LabeledFile],
) -> dict[str, Any]:
    item_by_path = {str(item.get("dicom_path", "")).strip(): item for item in items}
    file_details: list[dict[str, Any]] = []
    total_labels = 0
    total_full = 0
    total_line = 0
    total_value = 0
    total_label = 0
    total_prefix = 0
    files_with_predictions = 0

    for labeled in labeled_files:
        key = _canonical_path(labeled.path)
        item = item_by_path.get(key)
        predicted_measurements = item.get("measurements", []) if isinstance(item, dict) else []
        predictions: list[dict[str, str | None]] = []
        seen_prediction_keys: set[tuple[str, str, str]] = set()

        def _append_prediction(name: str | None, value: str | None, unit: str | None) -> None:
            prediction = {
                "name": name,
                "value": value,
                "unit": unit,
            }
            dedupe_key = (
                str(prediction["name"] or "").strip().lower(),
                str(prediction["value"] or "").strip().lower(),
                str(prediction["unit"] or "").strip().lower(),
            )
            if dedupe_key in seen_prediction_keys:
                return
            seen_prediction_keys.add(dedupe_key)
            predictions.append(prediction)

        for measurement in predicted_measurements if isinstance(predicted_measurements, list) else []:
            if not isinstance(measurement, dict):
                continue
            def _clean_value(key: str) -> str | None:
                raw = measurement.get(key)
                if raw is None:
                    return None
                text = str(raw).strip()
                return text or None

            _append_prediction(
                _clean_value("name"),
                _clean_value("value"),
                _clean_value("unit"),
            )

        raw_lines = item.get("line_predictions", []) if isinstance(item, dict) else []
        for line in raw_lines if isinstance(raw_lines, list) else []:
            if not isinstance(line, dict):
                continue
            line_text = str(line.get("text") or "").strip()
            if not line_text:
                continue
            _append_prediction(line_text, None, None)

        if predictions:
            files_with_predictions += 1

        matches = score_predictions(labeled.measurements, predictions)
        label_count = len(labeled.measurements)
        full_count = sum(1 for item in matches if item.full_match)
        line_count = sum(1 for item in matches if item.line_match)
        value_count = sum(1 for item in matches if item.value_match)
        match_label_count = sum(1 for item in matches if item.label_match)
        prefix_count = sum(1 for item in matches if item.prefix_match)

        total_labels += label_count
        total_full += full_count
        total_line += line_count
        total_value += value_count
        total_label += match_label_count
        total_prefix += prefix_count

        file_details.append(
            {
                "file_path": key,
                "file_name": labeled.file_name,
                "split": labeled.split,
                "status": str(item.get("status", "missing")) if isinstance(item, dict) else "missing",
                "error": item.get("error") if isinstance(item, dict) else "missing headless result",
                "expected_lines": [measurement.text for measurement in labeled.measurements],
                "predicted_measurements": predictions,
                "exact_matches": full_count,
                "line_matches": line_count,
                "value_matches": value_count,
                "label_matches": match_label_count,
                "prefix_matches": prefix_count,
                "total_labels": label_count,
                "matches": [
                    {
                        "expected_text": match.expected_text,
                        "predicted_text": match.predicted_text,
                        "line_match": match.line_match,
                        "prefix_match": match.prefix_match,
                        "label_match": match.label_match,
                        "value_match": match.value_match,
                        "unit_match": match.unit_match,
                        "full_match": match.full_match,
                    }
                    for match in matches
                ],
            }
        )

    labeled_file_count = len(labeled_files)
    return {
        "labeled_files": labeled_file_count,
        "files_with_predictions": files_with_predictions,
        "total_labels": total_labels,
        "exact_matches": total_full,
        "line_matches": total_line,
        "value_matches": total_value,
        "label_matches": total_label,
        "prefix_matches": total_prefix,
        "exact_match_rate": total_full / max(total_labels, 1),
        "line_match_rate": total_line / max(total_labels, 1),
        "value_match_rate": total_value / max(total_labels, 1),
        "label_match_rate": total_label / max(total_labels, 1),
        "prefix_match_rate": total_prefix / max(total_labels, 1),
        "detection_rate": files_with_predictions / max(labeled_file_count, 1),
        "file_details": file_details,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep preprocessing variants with the headless Echo OCR pipeline, save per-config "
            "JSON outputs for all DICOMs, and score the labeled subset against labels/labels.json."
        )
    )
    parser.add_argument("input_path", type=Path, help="DICOM file or directory root.")
    parser.add_argument("--pattern", default="*.dcm", help="Glob pattern for DICOM discovery.")
    parser.add_argument("--recursive", action="store_true", help="Use recursive discovery.")
    parser.add_argument("--max-files", type=int, default=0, help="Optional cap for discovery.")
    parser.add_argument(
        "--engine",
        default="tesseract",
        help="OCR engine to keep fixed during the sweep (default: tesseract).",
    )
    parser.add_argument(
        "--parser-mode",
        default="off",
        help="Parser mode passed to EchoOcrPipeline (default: off).",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=DEFAULT_LABELS_PATH,
        help="Ground-truth labels JSON used for scoring the labeled subset.",
    )
    parser.add_argument(
        "--split",
        default="validation",
        help="Optional label split filter, e.g. validation or train,validation.",
    )
    parser.add_argument(
        "--config-set",
        choices=("smoke", "broad", "order_matrix", "order_matrix_plan", "manifest"),
        default="broad",
        help=(
            "smoke/broad presets; order_matrix = factorial from --matrix-* flags; "
            "order_matrix_plan = fixed 8-row bin/up/order ablation (3× Lanczos vs cubic where upscale on); manifest = JSON."
        ),
    )
    parser.add_argument(
        "--config-manifest",
        type=Path,
        default=None,
        help="JSON file (array of {name, description, multiview_mode, default_view}) for config-set manifest.",
    )
    parser.add_argument(
        "--matrix-scales",
        default="1,2,3",
        help="Comma-separated scale factors for order_matrix (each 1–6).",
    )
    parser.add_argument(
        "--matrix-bin",
        default="none,otsu",
        help="Comma-separated bin modes for order_matrix: none, otsu.",
    )
    parser.add_argument(
        "--matrix-order",
        default="scale_then_threshold,threshold_then_scale",
        help="Comma-separated order tokens (st, ts, or full names) when bin is on.",
    )
    parser.add_argument(
        "--matrix-recipe",
        default="plain,unsharp",
        help="Comma-separated recipes for order_matrix: plain | unsharp.",
    )
    parser.add_argument(
        "--matrix-input",
        default="gray",
        help="Comma-separated input modes for order_matrix: gray | bgr.",
    )
    parser.add_argument(
        "--matrix-scale-algo",
        default="lanczos",
        help="Interpolation for continuous upscale in order_matrix.",
    )
    parser.add_argument(
        "--matrix-binary-scale-algo",
        default="nearest",
        help="Interpolation when upscaling after binarize (threshold_then_scale).",
    )
    parser.add_argument(
        "--matrix-multiview",
        default="none",
        help="Comma-separated multiview modes for order_matrix: none | pipeline (e.g. none,pipeline).",
    )
    parser.add_argument(
        "--matrix-no-morph-close",
        action="store_true",
        help="For order_matrix Otsu rows, disable morphological close.",
    )
    parser.add_argument(
        "--matrix-include-bin-1x",
        action="store_true",
        help="Include Otsu rows at scale 1 in order_matrix.",
    )
    parser.add_argument(
        "--restrict-from-label-scores",
        type=Path,
        default=None,
        help="Limit DICOMs to paths with a label line mismatch (split must match --split).",
    )
    parser.add_argument(
        "--restrict-dicom-paths-file",
        type=Path,
        default=None,
        help="One DICOM path per line (# comments ok); intersects with label-scores filter if both set.",
    )
    parser.add_argument(
        "--baseline-config",
        default="",
        help="Summary delta vs this config name; if empty, uses default_multiview when present.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write per-config artifacts and summary files.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip configs whose headless.json already exists in output-dir.",
    )
    parser.add_argument(
        "--resume-configs",
        action="store_true",
        help="Resume inside an in-progress config from checkpoint.json if present.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional frame cap passed to PipelineRequest.",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Write per-config checkpoint every N processed files (default: 10).",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10,
        help="Print progress every N processed files (default: 10).",
    )
    parser.add_argument(
        "--per-file-timeout-s",
        type=int,
        default=180,
        help="Fail and continue if one DICOM takes longer than this many seconds (0 disables timeout).",
    )
    parser.add_argument(
        "--only-configs",
        default="",
        help="Optional comma-separated config names to run.",
    )
    parser.add_argument(
        "--exclude-configs",
        default="",
        help="Optional comma-separated config names to skip.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input_path.expanduser()
    if not input_path.exists():
        print(f"Input path not found: {input_path}")
        return 2

    label_splits = parse_requested_splits(args.split)
    discovered = _discover_files(input_path, args.pattern, args.recursive)
    before_restrict = len(discovered)
    discovered = _restrict_discovered_paths(
        discovered,
        label_scores_path=args.restrict_from_label_scores,
        paths_file=args.restrict_dicom_paths_file,
        split_filter=label_splits,
    )
    if (
        before_restrict > len(discovered)
        and (args.restrict_from_label_scores or args.restrict_dicom_paths_file)
    ):
        print(f"Restrict filter: DICOMs {len(discovered)} (was {before_restrict}).")
    if args.max_files > 0:
        discovered = discovered[: args.max_files]
    if not discovered:
        print(
            "No matching DICOM files found. "
            f"input={_canonical_path(input_path)} pattern={args.pattern!r} "
            f"recursive={bool(args.recursive)} max_files={args.max_files or 'all'}"
        )
        if args.restrict_from_label_scores or args.restrict_dicom_paths_file:
            print("Restrict filters may have removed every path; check --split and filter files.")
        return 1

    labels_path = args.labels.expanduser()
    if not labels_path.exists():
        print(f"Labels file not found: {labels_path}")
        return 2

    labeled_files = parse_labels(labels_path, split_filter=label_splits)
    discovered_keys = {_canonical_path(path) for path in discovered}
    labeled_files = [item for item in labeled_files if _canonical_path(item.path) in discovered_keys]

    output_dir = args.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.config_set == "manifest":
        manifest_path = args.config_manifest.expanduser() if args.config_manifest else None
        if manifest_path is None or not manifest_path.is_file():
            print("config-set manifest requires --config-manifest pointing to a JSON file.")
            return 2
        try:
            configs = _load_manifest_configs(manifest_path)
        except ValueError as exc:
            print(exc)
            return 2
    elif args.config_set == "order_matrix":
        configs = _build_order_matrix_configs(args)
    elif args.config_set == "order_matrix_plan":
        configs = _order_matrix_plan_configs()
    else:
        configs = _select_configs(args.config_set)

    configs = _filter_configs(
        configs,
        only_configs=args.only_configs,
        exclude_configs=args.exclude_configs,
    )
    if not configs:
        print("No configs selected after filtering.")
        return 1
    print(f"Discovered DICOM files: {len(discovered)}")
    print(f"Labeled files in scope: {len(labeled_files)}")
    print(f"Configs to run: {len(configs)}")

    summary_rows: list[dict[str, Any]] = []
    summary_payload: list[dict[str, Any]] = []

    for index, config in enumerate(configs, start=1):
        config_dir = output_dir / config.name
        headless_path = config_dir / "headless.json"
        score_path = config_dir / "label_scores.json"
        checkpoint_path = _checkpoint_path_for(config_dir)
        if args.skip_existing and headless_path.exists() and score_path.exists():
            print(f"[{index}/{len(configs)}] skip existing: {config.name}")
            score_payload = json.loads(score_path.read_text(encoding="utf-8"))
            summary = score_payload.get("summary", {})
            summary_rows.append(
                {
                    "config_name": config.name,
                    "engine": args.engine,
                    "description": config.description,
                    "exact_match_rate": summary.get("exact_match_rate", 0.0),
                    "line_match_rate": summary.get("line_match_rate", 0.0),
                    "value_match_rate": summary.get("value_match_rate", 0.0),
                    "label_match_rate": summary.get("label_match_rate", 0.0),
                    "prefix_match_rate": summary.get("prefix_match_rate", 0.0),
                    "detection_rate": summary.get("detection_rate", 0.0),
                    "elapsed_s": summary.get("elapsed_s", 0.0),
                    "processed_files": summary.get("processed_files", 0),
                    "ok_files": summary.get("ok_files", 0),
                    "error_files": summary.get("error_files", 0),
                }
            )
            summary_payload.append(score_payload)
            continue

        print(f"[{index}/{len(configs)}] {config.name}")
        config_dir.mkdir(parents=True, exist_ok=True)
        started_at = _iso_now()
        elapsed_before = 0.0
        items: list[dict[str, Any]] = []
        if args.resume_configs and checkpoint_path.exists():
            items, checkpoint_manifest = _load_checkpoint(checkpoint_path)
            elapsed_before = float(checkpoint_manifest.get("elapsed_s", 0.0) or 0.0)
            started_at = str(checkpoint_manifest.get("started_at", started_at))
            print(f"  resumed checkpoint with {len(items)} processed files")

        processed_keys = {
            str(item.get("dicom_path", "")).strip()
            for item in items
            if str(item.get("dicom_path", "")).strip()
        }
        ok_files = sum(1 for item in items if item.get("status") == "ok")
        error_files = sum(1 for item in items if item.get("status") == "error")
        pending = [path for path in discovered if _canonical_path(path) not in processed_keys]
        started = time.perf_counter()
        pipeline: EchoOcrPipeline | None = _build_pipeline(args.engine, args.parser_mode, config)

        try:
            for path in pending:
                try:
                    result = _run_with_timeout(
                        int(args.per_file_timeout_s),
                        lambda _path=path, _pipeline=pipeline: _pipeline.run(
                            PipelineRequest(
                                dicom_path=_path,
                                parameters={"max_frames": args.max_frames},
                            )
                        ),
                    )
                    item = _result_to_item(path, result, config)
                except PerFileTimeoutError as exc:
                    item = _result_error_item(path, config, "Timeout", str(exc))
                    _dispose_pipeline(pipeline)
                    pipeline = _build_pipeline(args.engine, args.parser_mode, config)
                except KeyboardInterrupt:
                    elapsed_partial = elapsed_before + (time.perf_counter() - started)
                    _write_checkpoint(
                        checkpoint_path,
                        config=config,
                        items=items,
                        engine=args.engine,
                        parser_mode=args.parser_mode,
                        input_path=input_path,
                        started_at=started_at,
                        elapsed_s=elapsed_partial,
                        ok_files=ok_files,
                        error_files=error_files,
                    )
                    _dispose_pipeline(pipeline)
                    raise
                except Exception as exc:
                    item = _result_error_item(path, config, type(exc).__name__, str(exc))
                    _dispose_pipeline(pipeline)
                    pipeline = _build_pipeline(args.engine, args.parser_mode, config)

                items.append(item)
                if item["status"] == "ok":
                    ok_files += 1
                else:
                    error_files += 1

                processed_count = len(items)
                if (
                    processed_count % int(args.checkpoint_interval) == 0
                    or processed_count == len(discovered)
                ):
                    elapsed_partial = elapsed_before + (time.perf_counter() - started)
                    _write_checkpoint(
                        checkpoint_path,
                        config=config,
                        items=items,
                        engine=args.engine,
                        parser_mode=args.parser_mode,
                        input_path=input_path,
                        started_at=started_at,
                        elapsed_s=elapsed_partial,
                        ok_files=ok_files,
                        error_files=error_files,
                    )

                if processed_count % int(args.progress_interval) == 0 or processed_count == len(discovered):
                    print(
                        f"  files {processed_count}/{len(discovered)} "
                        f"ok={ok_files} error={error_files} "
                        f"last={path.name}"
                    )
        finally:
            _dispose_pipeline(pipeline)

        elapsed = elapsed_before + (time.perf_counter() - started)
        headless_payload = {
            "manifest": {
                "run_type": "preprocess_sweep_headless",
                "config_name": config.name,
                "config": asdict(config),
                "engine": args.engine,
                "parser_mode": args.parser_mode,
                "started_at": started_at,
                "elapsed_s": round(elapsed, 3),
                "input_path": _canonical_path(input_path),
                "summary": {
                    "processed_files": len(discovered),
                    "ok_files": ok_files,
                    "error_files": error_files,
                },
            },
            "items": items,
        }
        _write_json(headless_path, headless_payload)
        _clean_checkpoint(checkpoint_path)

        label_scores = _score_labeled_subset(items, labeled_files)
        score_payload = {
            "manifest": {
                "run_type": "preprocess_sweep_label_scores",
                "config_name": config.name,
                "config": asdict(config),
                "engine": args.engine,
                "labels_path": _canonical_path(labels_path),
                "split_filter": sorted(label_splits),
            },
            "summary": {
                **{key: value for key, value in label_scores.items() if key != "file_details"},
                "elapsed_s": round(elapsed, 3),
                "processed_files": len(discovered),
                "ok_files": ok_files,
                "error_files": error_files,
            },
            "file_details": label_scores["file_details"],
        }
        _write_json(score_path, score_payload)
        summary_payload.append(score_payload)

        summary_rows.append(
            {
                "config_name": config.name,
                "engine": args.engine,
                "description": config.description,
                "exact_match_rate": label_scores["exact_match_rate"],
                "line_match_rate": label_scores["line_match_rate"],
                "value_match_rate": label_scores["value_match_rate"],
                "label_match_rate": label_scores["label_match_rate"],
                "prefix_match_rate": label_scores["prefix_match_rate"],
                "detection_rate": label_scores["detection_rate"],
                "elapsed_s": round(elapsed, 3),
                "processed_files": len(discovered),
                "ok_files": ok_files,
                "error_files": error_files,
            }
        )

    explicit_baseline = str(args.baseline_config or "").strip()
    baseline_row = None
    effective_baseline_name = ""
    if explicit_baseline:
        baseline_row = next(
            (row for row in summary_rows if row["config_name"] == explicit_baseline),
            None,
        )
        if baseline_row is not None:
            effective_baseline_name = explicit_baseline
    if baseline_row is None:
        baseline_row = next(
            (row for row in summary_rows if row["config_name"] == "default_multiview"),
            None,
        )
        if baseline_row is not None:
            effective_baseline_name = "default_multiview"
    baseline_exact = float(baseline_row["exact_match_rate"]) if baseline_row is not None else None
    for row in summary_rows:
        row["delta_exact_vs_baseline"] = (
            round(float(row["exact_match_rate"]) - baseline_exact, 6)
            if baseline_exact is not None
            else ""
        )

    summary_rows = sorted(
        summary_rows,
        key=lambda row: (
            float(row["exact_match_rate"]),
            float(row["value_match_rate"]),
            -float(row["elapsed_s"]),
        ),
        reverse=True,
    )

    summary_json = {
        "manifest": {
            "run_type": "preprocess_sweep_summary",
            "input_path": _canonical_path(input_path),
            "labels_path": _canonical_path(labels_path),
            "engine": args.engine,
            "parser_mode": args.parser_mode,
            "config_set": args.config_set,
            "baseline_config": effective_baseline_name,
            "config_count": len(configs),
            "file_count": len(discovered),
            "labeled_file_count": len(labeled_files),
        },
        "results": summary_rows,
    }
    _write_json(output_dir / "summary.json", summary_json)
    _write_csv(
        output_dir / "summary.csv",
        summary_rows,
        [
            "config_name",
            "engine",
            "description",
            "exact_match_rate",
            "line_match_rate",
            "value_match_rate",
            "label_match_rate",
            "prefix_match_rate",
            "detection_rate",
            "delta_exact_vs_baseline",
            "elapsed_s",
            "processed_files",
            "ok_files",
            "error_files",
        ],
    )

    if summary_rows:
        best = summary_rows[0]
        print("\nBest config")
        print(
            f"  {best['config_name']}: exact={best['exact_match_rate']:.3f} "
            f"value={best['value_match_rate']:.3f} elapsed={best['elapsed_s']:.1f}s"
        )
    print(f"Summary written to: {output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
