## Validation failure sweep

### Bash

```bash
cd /path/to/Master

export GLM_OCR_RUNNER=mamba
export GLM_OCR_ENV=glm_ocr   # adjust if your GLM env name differs

mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless \
  /path/to/dicom/root \
  --recursive \
  --engine glm-ocr \
  --config-set broad \
  --labels labels/labels.json \
  --split validation \
  --only-configs gray_x3_lanczos \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4

mamba run -n DL python -m app.tools.batch.export_validation_failures \
  artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4/gray_x3_lanczos/label_scores.json
```

### PowerShell

Use `$env:NAME = "value"` instead of `export`, and use the backtick `` ` `` for line continuation.

```powershell
cd C:\Users\G513\Documents\howest\Semester_5\Stage\StageOpdracht\Master

$env:GLM_OCR_RUNNER = "mamba"
$env:GLM_OCR_ENV = "glm_ocr"

$DicomRoot = "C:\Users\G513\Documents\howest\Semester_5\Stage\StageOpdracht\database_stage\files\p10"

mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless `
  $DicomRoot `
  --recursive `
  --engine glm-ocr `
  --config-set broad `
  --labels labels/labels.json `
  --split validation `
  --only-configs gray_x3_lanczos `
  --output-dir artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4

mamba run -n DL python -m app.tools.batch.export_validation_failures `
  artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4/gray_x3_lanczos/label_scores.json
```

One-line PowerShell is also fine if you prefer not to use continuations.
