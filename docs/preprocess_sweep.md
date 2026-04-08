# Preprocessing Sweep

This sweep keeps ROI detection and line segmentation unchanged and varies only the line OCR preprocessing path:

- Step 6: the default per-line preprocessing chain
- Step 7: whether the transcriber also retries alternate views (`high_contrast`, `clahe`)

The sweep writes:

- one `headless.json` per config with all discovered DICOM outputs
- one `label_scores.json` per config for the labeled subset from `labels/labels.json`
- a top-level `summary.json` and `summary.csv` ranking configs

## What Step 7 Does

Step 7 is not another segmentation pass. It is a conditional multiview retry inside `LineTranscriber`:

- `default`: the main preprocessed line image
- `high_contrast`: equalize + adaptive threshold variant
- `clahe`: CLAHE + Otsu variant

Those alternates are only tried when the first pass looks weak or structurally suspicious.

## Smoke Test

```bash
mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless \
  /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10003731 \
  --recursive \
  --config-set smoke \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_smoke
```

## Full Five-Patient Sweep

This runs the broader curated config set over all DICOMs under the five patient folders.

```bash
mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless \
  /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10 \
  --recursive \
  --engine tesseract \
  --config-set broad \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_tesseract_broad
```

## Validation workflow (labels → failures → sweep)

1. Label measurements in the GUI; ground truth lives in `labels/labels.json` (train/validation splits).
2. Run a sweep; each config writes `label_scores.json` with per-line match detail; `summary.csv` ranks configs by exact/value match rate on the labeled subset.
3. For mismatches, use `python -m app.tools.batch.export_validation_failures path/to/label_scores.json` for `validation_exact_failures.csv`, or `notebooks/validation_failure_walkthrough.ipynb` for visual replay.
4. Iterate: try `--config-set order_matrix` or `--config-set manifest` with `--engine glm-ocr` (or `tesseract`, etc.) to compare preprocessing and engines on the same DICOMs.

## Full “everything” sweep (script)

From the repo root, after setting `SWEEP_DICOM_ROOT`:

```bash
export SWEEP_DICOM_ROOT="/path/to/dicoms"
export GLM_OCR_RUNNER=mamba GLM_OCR_ENV=glm_ocr
export SURYA_RUNNER=mamba SURYA_ENV=surya
bash scripts/run_full_preprocess_sweep.sh
```

This runs **glm-ocr**, **tesseract**, and **surya** each with **two** runs: Otsu morph close on vs off; `order_matrix` uses scales **1–6**, **gray+bgr**, **plain+unsharp**, **none+otsu**, both preprocess orders, **none+pipeline** multiview, **bin at 1×** included, Lanczos + nearest binary upscale, validation scoring, resume/checkpoint/skip-existing. Outputs land under `artifacts/ocr_redesign/full_order_matrix_<UTC>/`.

That grid is **144 configs per** (engine × morph) because `2×2×2×(6 + 6×2) = 144` (multiview × input × recipe × (no-bin scales + Otsu scales × two orders)). For a **fixed 8-config** ablation (same bin/up/order structure as before, plus **3× Lanczos vs 3× cubic** on every upscaled path), use **`--config-set order_matrix_plan`** or `bash scripts/run_plan_preprocess_sweep.sh`. Config names spell out the recipe: `plan_no_binarize_*`, `plan_scale_then_otsu_*` (grayscale upscale then Otsu), `plan_otsu_then_scale_*` (Otsu at 1× then binary upscale), with `_1x`, `_3x_lanczos`, or `_3x_cubic`.

Config folder names include `mv0` (no multiview) / `mv1` (pipeline multiview). Override engines: `SWEEP_ENGINES="tesseract"` Smoke: `SWEEP_EXTRA="--max-files 1"`.

## Parameterized order matrix

Builds configs from flags (Cartesian product with pruning: no binarization uses only `scale_then_threshold`; Otsu at scale 1 is omitted unless `--matrix-include-bin-1x`).

```bash
mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless \
  /path/to/dicom_root \
  --recursive \
  --engine glm-ocr \
  --config-set order_matrix \
  --matrix-scales 1,2,3 \
  --matrix-bin none,otsu \
  --matrix-order scale_then_threshold,threshold_then_scale \
  --matrix-recipe plain,unsharp \
  --matrix-input gray,bgr \
  --output-dir artifacts/ocr_redesign/order_matrix_glm
```

Relevant flags: `--matrix-scale-algo`, `--matrix-binary-scale-algo` (default `nearest` for upscaling **after** Otsu), `--matrix-multiview`, `--matrix-no-morph-close`, `--only-configs`, `--exclude-configs`.

## JSON manifest configs

Use `--config-set manifest --config-manifest path.json` where the file is a JSON array of objects: `name`, `description`, optional `multiview_mode` (`none` or `pipeline`), and `default_view` (fields of `PreprocessSpec`: `input_mode`, `scale_factor`, `scale_algo`, `threshold_mode`, `preprocess_order`, `binary_scale_algo`, etc.).

## Faster runs on failing DICOMs only

- `--restrict-from-label-scores path/to/label_scores.json` — keep only paths in the given split (`--split`) that have at least one `full_match: false` line.
- `--restrict-dicom-paths-file paths.txt` — one absolute or resolvable DICOM path per line (`#` comments allowed). If both restrict flags are set, the intersection is used.

## Summary baseline column

`summary.csv` includes `delta_exact_vs_baseline`. Use `--baseline-config my_cfg_name` to compare against a named row; if omitted, the tool falls back to `default_multiview` when that config appears in the same run.

## Notes

- The default sweep engine is `tesseract` to isolate preprocessing effects with a fast, stable OCR backend.
- To test another engine, pass `--engine glm-ocr` or `--engine surya`.
- `summary.csv` is the quickest file to sort by exact/value match rate.
- For long GLM runs, use `--resume-configs --skip-existing --checkpoint-interval 10 --progress-interval 10`.
- To rerun only one problematic config, use `--only-configs otsu_close_x3_lanczos_no_unsharp`.
- `--per-file-timeout-s 180` marks a stuck DICOM as an error, checkpoints progress, rebuilds the worker, and continues.
- `PreprocessSpec` supports `input_mode` `gray` (default) vs `bgr` (color line crop until threshold), `preprocess_order` `scale_then_threshold` vs `threshold_then_scale`, and `binary_scale_algo` for the second upsample after binarization.
