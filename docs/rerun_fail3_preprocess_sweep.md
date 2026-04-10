# Rerun: 3 Failing Validation Files Across All Preprocessing Profiles

This runbook executes the full `broad` preprocessing sweep on only the current 3 failing validation DICOMs, then saves all artifacts (including non-improving runs) for research reporting.

## What this does

- Finds failing validation entries from:
  - `artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4/gray_x3_lanczos/label_scores.json`
- Resolves those file names under your dataset root
- Runs all preprocessing profiles in `--config-set broad` (including added experimental profiles for dropped leading digits)
- Writes timestamped output under `artifacts/ocr_redesign/`
- Saves progress continuously via checkpoints (`--checkpoint-interval 1`)

## PowerShell command (copy/paste)

```powershell
Set-Location "C:\Users\G513\Documents\howest\Semester_5\Stage\StageOpdracht\Master"

$TS = Get-Date -Format "yyyyMMddTHHmmss"
$OUT = "artifacts/ocr_redesign/preprocess_sweep_glm_fail3_broad_$TS"
$SRC = "artifacts/ocr_redesign/preprocess_sweep_glm_broad_v4/gray_x3_lanczos/label_scores.json"
$DATA_ROOT = "C:\Users\G513\Documents\howest\Semester_5\Stage\StageOpdracht"
$NAMES = Join-Path $OUT "fail3_names.txt"
$PATHS = Join-Path $OUT "fail3_paths.txt"

New-Item -ItemType Directory -Force -Path $OUT | Out-Null

@"
import json
from pathlib import Path

src = Path(r"$SRC")
names_out = Path(r"$NAMES")
paths_out = Path(r"$PATHS")
root = Path(r"$DATA_ROOT")

data = json.loads(src.read_text(encoding="utf-8"))

names = []
for fd in data.get("file_details", []):
    if fd.get("split") != "validation":
        continue
    matches = fd.get("matches") or []
    if not any(isinstance(m, dict) and not bool(m.get("full_match", True)) for m in matches):
        continue
    fn = (fd.get("file_name") or "").strip()
    if fn:
        names.append(fn)

uniq_names = []
seen = set()
for n in names:
    if n not in seen:
        seen.add(n)
        uniq_names.append(n)

resolved = []
for n in uniq_names:
    hits = list(root.rglob(n))
    if hits:
        resolved.append(str(hits[0].resolve()))

names_out.write_text("\n".join(uniq_names) + ("\n" if uniq_names else ""), encoding="utf-8")
paths_out.write_text("\n".join(resolved) + ("\n" if resolved else ""), encoding="utf-8")

print(f"Failing names: {len(uniq_names)}")
print(f"Resolved paths: {len(resolved)}")
print(f"Names file: {names_out}")
print(f"Paths file: {paths_out}")
"@ | mamba run -n DL python -

Get-Content $NAMES
Get-Content $PATHS

$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"

mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless `
  "$DATA_ROOT" `
  --only-labeled `
  --engine glm-ocr `
  --config-set broad `
  --labels labels/labels.json `
  --split validation `
  --restrict-dicom-paths-file "$PATHS" `
  --output-dir "$OUT" `
  --checkpoint-interval 1 `
  --progress-interval 1 `
  --resume-configs
```

## Output files to include in research

Inside `$OUT`:

- `summary.json`
- `summary.csv`
- `line_match_details_all_configs.csv` (expected vs predicted line text + match flags)
- `fail3_names.txt`
- `fail3_paths.txt`
- Per profile folder:
  - `headless.json`
  - `label_scores.json`
  - `line_match_details.csv`
  - `checkpoint.json` (while running)

## Quick rerun notes

- You can rerun this as often as needed; each run gets a new timestamped output folder.
- Even if no profile improves results, the run still generates reportable artifacts.
- If a run stops, rerun the same command block and it will resume per config because `--resume-configs` is enabled.

## Engine-specific runs (same 3 files)

Use the same `$PATHS` file and switch `--engine`:

```powershell
# Tesseract
mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless `
  "$DATA_ROOT" `
  --only-labeled `
  --engine tesseract `
  --config-set broad `
  --labels labels/labels.json `
  --split validation `
  --restrict-dicom-paths-file "$PATHS" `
  --output-dir "artifacts/ocr_redesign/preprocess_sweep_tesseract_fail3_broad_$TS" `
  --checkpoint-interval 1 `
  --progress-interval 1 `
  --resume-configs

# EasyOCR (full)
mamba run -n DL python -m app.tools.batch.sweep_preprocessing_headless `
  "$DATA_ROOT" `
  --only-labeled `
  --engine easyocr `
  --config-set broad `
  --labels labels/labels.json `
  --split validation `
  --restrict-dicom-paths-file "$PATHS" `
  --output-dir "artifacts/ocr_redesign/preprocess_sweep_easyocr_fail3_broad_$TS" `
  --checkpoint-interval 1 `
  --progress-interval 1 `
  --resume-configs
```

### If Tesseract shows "libcurl.dll not found" on Windows

```powershell
mamba install -n DL -c conda-forge -y libcurl curl tesseract
mamba run -n DL tesseract --version
```

## Added experimental profiles in `broad`

- `gray_x4_nearest`
- `gray_x4_lanczos`
- `unsharp_mild_x3_lanczos`
- `median3_gray_x3_lanczos`
- `clahe_gray_x3_no_bin`
- `adaptive_weak_single`
- `otsu_then_scale_x3_nearest_no_close`
- `otsu_then_scale_x4_nearest_no_close`
- `invert_gray_x3_lanczos`
