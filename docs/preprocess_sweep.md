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
mamba run -n DL python -m app.tools.sweep_preprocessing_headless \
  /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/p10003731 \
  --recursive \
  --config-set smoke \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_smoke
```

## Full Five-Patient Sweep

This runs the broader curated config set over all DICOMs under the five patient folders.

```bash
mamba run -n DL python -m app.tools.sweep_preprocessing_headless \
  /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10 \
  --recursive \
  --engine tesseract \
  --config-set broad \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_tesseract_broad
```

## Notes

- The default sweep engine is `tesseract` to isolate preprocessing effects with a fast, stable OCR backend.
- To test another engine, pass `--engine glm-ocr` or `--engine surya`.
- `summary.csv` is the quickest file to sort by exact/value match rate.
- For long GLM runs, use `--resume-configs --skip-existing --checkpoint-interval 10 --progress-interval 10`.
- To rerun only one problematic config, use `--only-configs otsu_close_x3_lanczos_no_unsharp`.
- `--per-file-timeout-s 180` marks a stuck DICOM as an error, checkpoints progress, rebuilds the worker, and continues.
