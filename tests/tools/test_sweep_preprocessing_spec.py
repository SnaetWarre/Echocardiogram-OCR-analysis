from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.tools.batch.sweep_preprocessing_headless import (
    PreprocessSpec,
    SweepConfig,
    _build_order_matrix_configs,
    _build_headless_run_payload,
    _build_label_scores_payload,
    _order_matrix_plan_configs,
    _preprocess_with_spec,
    _restrict_discovered_paths,
    preprocess_spec_from_dict,
)


def test_preprocess_gray_scale_then_otsu_shape() -> None:
    img = np.random.randint(10, 245, (4, 20), dtype=np.uint8)
    spec = PreprocessSpec(
        scale_factor=2,
        scale_algo="nearest",
        threshold_mode="otsu",
        preprocess_order="scale_then_threshold",
        morph_close=False,
    )
    out = _preprocess_with_spec(img, spec)
    assert out.ndim == 2
    assert out.shape == (8, 40)


def test_preprocess_bgr_no_bin_three_channels() -> None:
    gray = np.random.randint(10, 245, (2, 10), dtype=np.uint8)
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    spec = PreprocessSpec(
        input_mode="bgr",
        scale_factor=2,
        scale_algo="nearest",
        threshold_mode="none",
    )
    out = _preprocess_with_spec(bgr, spec)
    assert out.ndim == 3
    assert out.shape[2] == 3
    assert out.shape[:2] == (4, 20)


def test_bgr_matches_gray_when_threshold_none_same_scale() -> None:
    rng = np.random.default_rng(0)
    gray = rng.integers(10, 245, (3, 15), dtype=np.uint8)
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    spec_gray = PreprocessSpec(
        input_mode="gray",
        scale_factor=2,
        scale_algo="nearest",
        threshold_mode="none",
    )
    spec_bgr = PreprocessSpec(
        input_mode="bgr",
        scale_factor=2,
        scale_algo="nearest",
        threshold_mode="none",
    )
    gout = _preprocess_with_spec(gray, spec_gray)
    bout = _preprocess_with_spec(bgr, spec_bgr)
    assert bout.ndim == 3
    assert np.array_equal(gout, bout[:, :, 0])
    assert np.array_equal(bout[:, :, 0], bout[:, :, 1])
    assert np.array_equal(bout[:, :, 0], bout[:, :, 2])


def test_threshold_then_scale_is_binary() -> None:
    img = np.random.randint(10, 245, (4, 12), dtype=np.uint8)
    spec = PreprocessSpec(
        scale_factor=2,
        scale_algo="lanczos",
        binary_scale_algo="nearest",
        threshold_mode="otsu",
        preprocess_order="threshold_then_scale",
        morph_close=False,
    )
    out = _preprocess_with_spec(img, spec)
    assert out.ndim == 2
    uniq = set(np.unique(out).tolist())
    assert uniq.issubset({0, 255})


def test_empty_roi() -> None:
    empty = np.zeros((0, 0), dtype=np.uint8)
    out = _preprocess_with_spec(empty, PreprocessSpec())
    assert out.size == 0


def test_preprocess_spec_from_dict_fills_defaults() -> None:
    spec = preprocess_spec_from_dict({"scale_factor": 3})
    assert spec.input_mode == "gray"
    assert spec.preprocess_order == "scale_then_threshold"
    assert spec.scale_factor == 3


def test_order_matrix_only_no_bin() -> None:
    args = SimpleNamespace(
        matrix_scales="1,2",
        matrix_bin="none",
        matrix_order="st,ts",
        matrix_recipe="plain",
        matrix_input="gray",
        matrix_scale_algo="lanczos",
        matrix_binary_scale_algo="nearest",
        matrix_multiview="none",
        matrix_no_morph_close=False,
        matrix_include_bin_1x=False,
    )
    cfgs = _build_order_matrix_configs(args)
    assert len(cfgs) == 2
    names = {c.name for c in cfgs}
    assert names == {"om_gray_pln_s1_nbin_st_mv0", "om_gray_pln_s2_nbin_st_mv0"}


def test_order_matrix_otsu_two_orders() -> None:
    args = SimpleNamespace(
        matrix_scales="2",
        matrix_bin="otsu",
        matrix_order="st,ts",
        matrix_recipe="plain",
        matrix_input="gray",
        matrix_scale_algo="lanczos",
        matrix_binary_scale_algo="nearest",
        matrix_multiview="none",
        matrix_no_morph_close=False,
        matrix_include_bin_1x=False,
    )
    cfgs = _build_order_matrix_configs(args)
    assert len(cfgs) == 2
    names = {c.name for c in cfgs}
    assert "om_gray_pln_s2_otsu_st_mc_mv0" in names
    assert "om_gray_pln_s2_otsu_ts_mc_mv0" in names


def test_order_matrix_plan_preset_size() -> None:
    cfgs = _order_matrix_plan_configs()
    assert len(cfgs) == 8
    assert [c.name for c in cfgs] == [
        "plan_no_binarize_1x",
        "plan_no_binarize_3x_lanczos",
        "plan_no_binarize_3x_cubic",
        "plan_scale_then_otsu_1x",
        "plan_scale_then_otsu_3x_lanczos",
        "plan_scale_then_otsu_3x_cubic",
        "plan_otsu_then_scale_3x_lanczos",
        "plan_otsu_then_scale_3x_cubic",
    ]
    assert {c.default_view.input_mode for c in cfgs} == {"gray"}
    assert {c.default_view.scale_algo for c in cfgs} == {"lanczos", "cubic"}
    st_s3 = next(c for c in cfgs if c.name == "plan_scale_then_otsu_3x_lanczos")
    ts_s3 = next(c for c in cfgs if c.name == "plan_otsu_then_scale_3x_lanczos")
    assert st_s3.default_view.preprocess_order == "scale_then_threshold"
    assert ts_s3.default_view.preprocess_order == "threshold_then_scale"
    assert next(c for c in cfgs if c.name == "plan_no_binarize_3x_cubic").default_view.scale_algo == "cubic"


def test_order_matrix_multiview_expands_names() -> None:
    args = SimpleNamespace(
        matrix_scales="2",
        matrix_bin="none",
        matrix_order="st",
        matrix_recipe="plain",
        matrix_input="gray",
        matrix_scale_algo="lanczos",
        matrix_binary_scale_algo="nearest",
        matrix_multiview="none,pipeline",
        matrix_no_morph_close=False,
        matrix_include_bin_1x=False,
    )
    cfgs = _build_order_matrix_configs(args)
    assert len(cfgs) == 2
    names = {c.name for c in cfgs}
    assert names == {"om_gray_pln_s2_nbin_st_mv0", "om_gray_pln_s2_nbin_st_mv1"}
    assert {c.multiview_mode for c in cfgs} == {"none", "pipeline"}


def test_restrict_from_label_scores(tmp_path: Path) -> None:
    bad = tmp_path / "bad.dcm"
    bad.write_bytes(b"")
    other = tmp_path / "other.dcm"
    other.write_bytes(b"")
    ls = tmp_path / "ls.json"
    ls.write_text(
        json.dumps(
            {
                "file_details": [
                    {
                        "split": "validation",
                        "file_path": str(bad.resolve()),
                        "matches": [{"full_match": False}],
                    },
                    {
                        "split": "validation",
                        "file_path": str(other.resolve()),
                        "matches": [{"full_match": True}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    disc = [bad, other]
    out = _restrict_discovered_paths(
        disc,
        label_scores_path=ls,
        paths_file=None,
        split_filter={"validation"},
    )
    assert len(out) == 1
    assert out[0].resolve() == bad.resolve()


@pytest.mark.parametrize(
    "order",
    ["scale_then_threshold", "threshold_then_scale"],
)
def test_threshold_none_ignores_order(order: str) -> None:
    img = np.ones((2, 8), dtype=np.uint8) * 100
    a = _preprocess_with_spec(
        img,
        PreprocessSpec(scale_factor=2, scale_algo="nearest", threshold_mode="none", preprocess_order=order),
    )
    b = _preprocess_with_spec(
        img,
        PreprocessSpec(
            scale_factor=2,
            scale_algo="nearest",
            threshold_mode="none",
            preprocess_order="scale_then_threshold",
        ),
    )
    assert np.array_equal(a, b)


def test_headless_payload_contains_issues_only_section() -> None:
    config = SweepConfig(
        name="x",
        description="x",
        default_view=PreprocessSpec(),
    )
    payload = _build_headless_run_payload(
        config,
        [
            {
                "dicom_path": "C:/a.dcm",
                "status": "ok",
                "measurements": [
                    {
                        "name": "LVOT maxPG",
                        "raw_ocr_text": "LVOT maxPG 2 mmHg",
                        "value": "12",
                        "corrected_value": "12",
                        "flags": ["implausible_value", "rule_recovered_leading_digit"],
                    }
                ],
            },
            {
                "dicom_path": "C:/b.dcm",
                "status": "error",
                "measurements": [],
                "error": {"type": "RuntimeError", "message": "boom"},
            },
        ],
        engine="glm-ocr",
        input_path=Path("."),
        started_at="2026-01-01T00:00:00Z",
        elapsed_s=1.0,
        ok_files=1,
        error_files=1,
        discovered_count=2,
    )

    assert payload["issues_only"]["summary"]["error_item_count"] == 1
    assert payload["issues_only"]["summary"]["flagged_measurement_count"] == 1


def test_label_scores_payload_contains_mismatched_lines_issues_only() -> None:
    config = SweepConfig(
        name="x",
        description="x",
        default_view=PreprocessSpec(),
    )
    label_scores = {
        "labeled_files": 1,
        "files_with_predictions": 1,
        "total_labels": 1,
        "exact_matches": 0,
        "line_matches": 0,
        "value_matches": 0,
        "label_matches": 1,
        "prefix_matches": 1,
        "exact_match_rate": 0.0,
        "line_match_rate": 0.0,
        "value_match_rate": 0.0,
        "label_match_rate": 1.0,
        "prefix_match_rate": 1.0,
        "detection_rate": 1.0,
        "file_details": [
            {
                "file_name": "x.dcm",
                "file_path": "C:/x.dcm",
                "split": "validation",
                "status": "ok",
                "error": None,
                "matches": [
                    {
                        "expected_text": "%FS 16 %",
                        "predicted_text": "%FS 6 %",
                        "label_match": True,
                        "value_match": False,
                        "unit_match": True,
                        "prefix_match": True,
                        "full_match": False,
                    }
                ],
            }
        ],
    }
    payload = _build_label_scores_payload(
        config,
        label_scores,
        engine="glm-ocr",
        labels_path=Path("labels.json"),
        label_splits={"validation"},
        elapsed_s=1.0,
        discovered_count=1,
        ok_files=1,
        error_files=0,
    )

    assert payload["issues_only"]["summary"]["mismatched_line_count"] == 1
    assert payload["issues_only"]["mismatched_lines"][0]["predicted_text"] == "%FS 6 %"
