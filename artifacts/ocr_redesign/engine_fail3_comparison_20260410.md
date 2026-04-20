# Engine comparison on 3 persistent validation failures (2026-04-10)

## Runs

- GLM broad sweep: `artifacts/ocr_redesign/preprocess_sweep_glm_fail3_broad_20260410T114939`
- Tesseract broad sweep: `artifacts/ocr_redesign/preprocess_sweep_tesseract_fail3_broad_20260410T131140`
- EasyOCR focused sweep (gray_x3_lanczos + default_multiview): `artifacts/ocr_redesign/preprocess_sweep_easyocr_fail3_focus_20260410T131556`

## Target lines

1. `92290733_0004.dcm` line 3: expected `%FS 16 %`
2. `91243943_0052.dcm` line 1: expected `LVOT maxPG 12 mmHg`
3. `91243943_0053.dcm` line 4: expected `AV maxPG 16 mmHg`

## Outcomes

### GLM (gray_x3_lanczos)

- `%FS 16 %` -> `%FS 6 %` (no)
- `LVOT maxPG 12 mmHg` -> `LVOT maxPG 2 mmHg` (no)
- `AV maxPG 16 mmHg` -> `AV maxPG 6 mmHg` (no)
- Matched target lines: **0/3**

### Tesseract (no_preprocess_gray)

- `%FS 16 %` -> `FS 16` (format mismatch, no)
- `LVOT maxPG 12 mmHg` -> `LVOT maxPG 12` (unit missing, no)
- `AV maxPG 16 mmHg` -> `AV maxPG 16 mmHg` (yes)
- Matched target lines: **1/3**

### EasyOCR (gray_x3_lanczos)

- `%FS 16 %` -> `%FS 6 %` (no)
- `LVOT maxPG 12 mmHg` -> `LVOT maxPG 2 mmHg` (no)
- `AV maxPG 16 mmHg` -> `AV maxPG 6 mmHg` (no)
- Matched target lines: **0/3**

### EasyOCR (default_multiview)

- `%FS 16 %` -> `%FS 6 %` (no)
- `LVOT maxPG 12 mmHg` -> `LVOT maxPG 2 mmHg` (no)
- `AV maxPG 16 mmHg` -> `AV maxPG 6 mmHg` (no)
- Matched target lines: **0/3**

## Notes

- Tesseract runtime issue (`libcurl.dll` missing) was fixed in the `DL` environment via:
  - `mamba install -n DL -c conda-forge -y libcurl curl tesseract`
- `envs/dl.yml` now includes `easyocr==1.7.2` to keep this reproducible.
