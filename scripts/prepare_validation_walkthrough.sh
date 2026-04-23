#!/usr/bin/env bash
# After a preprocess sweep, write validation_exact_failures.csv next to the sweep folder
# and point `notebooks/validation_failure_walkthrough.ipynb` at the same SWEEP_STEM
# (set SWEEP_STEM in the first code cell, or keep the repo default if it matches).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO}"
SWEEP_STEM="${SWEEP_STEM:-preprocess_sweep_glm_broad_v5_charfb}"
LABEL_SCORES="${REPO}/artifacts/ocr_redesign/${SWEEP_STEM}/gray_x3_lanczos/label_scores.json"

if [[ ! -f "${LABEL_SCORES}" ]]; then
  echo "Missing: ${LABEL_SCORES}" >&2
  echo "Run sweep_preprocessing_headless with --output-dir artifacts/ocr_redesign/${SWEEP_STEM} first." >&2
  exit 2
fi

PYTHON="${PYTHON:-$(command -v python3)}"

"${PYTHON}" -m app.tools.batch.export_validation_failures "${LABEL_SCORES}"
OUT="${REPO}/artifacts/ocr_redesign/${SWEEP_STEM}/validation_exact_failures.csv"
echo "CSV: ${OUT}"

echo
echo "Notebook: set in the first code cell (or match repo default):"
echo "  SWEEP_STEM = \"${SWEEP_STEM}\""
echo
echo "DICOMs on an external drive (so path resolution + inspection find files):"
echo "  export ECHO_OCR_DICOM_ROOT=/run/media/warre/T7/MIMIC-IV-ECHO"
echo "  (adjust to your mount; parent of \`files/p10\` or the whole dataset root you use with rglob.)"
echo
echo "Then restart the notebook kernel and run all cells from the top."
