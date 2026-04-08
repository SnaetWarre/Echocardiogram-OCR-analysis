#!/usr/bin/env bash
# Maximal headless preprocessing sweep: order_matrix × engines × (morph on/off).
#
# Why 144 configs per engine/morph run?
#   2 multiview (none,pipeline) × 2 input (gray,bgr) × 2 recipe (plain,unsharp)
#   × (6 no-bin scales + 6 otsu scales × 2 orders) = 2×2×2×18 = 144.
# For the fixed 8-config plan (Lanczos vs cubic on 3× paths), use: --config-set order_matrix_plan
#   or: bash scripts/run_plan_preprocess_sweep.sh
#
# Prerequisites (typical):
#   bash scripts/bootstrap_headless_env.sh
#
# GLM worker uses env `glm_ocr` by default (see app/pipeline/ocr/ocr_engines.py):
#   export GLM_OCR_RUNNER=mamba
#   export GLM_OCR_ENV=glm_ocr
#
# Surya worker:
#   export SURYA_RUNNER=mamba
#   export SURYA_ENV=surya
#
# Usage:
#   export SWEEP_DICOM_ROOT="/path/to/dicoms_or_patient_folder"
#   bash scripts/run_full_preprocess_sweep.sh
#
# Optional env:
#   SWEEP_OUTPUT_PARENT  — default: <repo>/artifacts/ocr_redesign
#   SWEEP_MAMBA_ENV      — default: DL
#   SWEEP_ENGINES        — space-separated, default: "glm-ocr tesseract surya"
#   SWEEP_EXTRA          — extra args passed to every sweep (e.g. --max-files 2 for smoke)
#   SKIP_EXISTING=0      — set to 0 to disable --skip-existing

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v mamba >/dev/null 2>&1 && ! command -v conda >/dev/null 2>&1; then
  echo "Need mamba or conda in PATH."
  exit 1
fi

RUNNER=(mamba)
if ! command -v mamba >/dev/null 2>&1; then
  RUNNER=(conda)
fi

MAMBA_ENV="${SWEEP_MAMBA_ENV:-DL}"
PY=("${RUNNER[@]}" "run" "-n" "${MAMBA_ENV}" "python")

: "${SWEEP_DICOM_ROOT:=}"
if [[ -z "${SWEEP_DICOM_ROOT}" || "${SWEEP_DICOM_ROOT}" == "..." ]]; then
  echo "Set SWEEP_DICOM_ROOT to a real path (not literal ...)."
  echo "Example: export EXACT_ROOT=\"/path/to/p10\""
  echo "Then:     export SWEEP_DICOM_ROOT=\"\${EXACT_ROOT}\""
  exit 2
fi
if [[ ! -e "${SWEEP_DICOM_ROOT}" ]]; then
  echo "SWEEP_DICOM_ROOT does not exist: ${SWEEP_DICOM_ROOT}"
  exit 2
fi
# Quick sanity: at least one *.dcm / *.DCM under tree when using default sweep pattern
if [[ -d "${SWEEP_DICOM_ROOT}" ]]; then
  _n="$(find "${SWEEP_DICOM_ROOT}" -type f -iname '*.dcm' -print -quit 2>/dev/null | wc -l)"
  if [[ "${_n}" -eq 0 ]]; then
    echo "No .dcm files found under: ${SWEEP_DICOM_ROOT}"
    echo "Point SWEEP_DICOM_ROOT at a folder that contains DICOMs, or at a single .dcm file."
    exit 2
  fi
fi

OUT_PARENT="${SWEEP_OUTPUT_PARENT:-${ROOT_DIR}/artifacts/ocr_redesign}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ROOT="${OUT_PARENT}/full_order_matrix_${STAMP}"
mkdir -p "${RUN_ROOT}"

ENGINES=(glm-ocr tesseract surya)
if [[ -n "${SWEEP_ENGINES:-}" ]]; then
  read -r -a ENGINES <<< "${SWEEP_ENGINES}"
fi

SKIP_FLAG=(--skip-existing)
if [[ "${SKIP_EXISTING:-1}" == "0" ]]; then
  SKIP_FLAG=()
fi

EXTRA=()
if [[ -n "${SWEEP_EXTRA:-}" ]]; then
  read -r -a EXTRA <<< "${SWEEP_EXTRA}"
fi

common_args=(
  "${SWEEP_DICOM_ROOT}"
  --recursive
  --config-set order_matrix
  --matrix-scales "1,2,3,4,5,6"
  --matrix-bin "none,otsu"
  --matrix-order "scale_then_threshold,threshold_then_scale"
  --matrix-recipe "plain,unsharp"
  --matrix-input "gray,bgr"
  --matrix-scale-algo lanczos
  --matrix-binary-scale-algo nearest
  --matrix-multiview "none,pipeline"
  --matrix-include-bin-1x
  --split validation
  --checkpoint-interval 10
  --progress-interval 10
  --per-file-timeout-s 180
  --resume-configs
  "${SKIP_FLAG[@]}"
  "${EXTRA[@]}"
)

echo "Run root: ${RUN_ROOT}"
echo "DICOM input: ${SWEEP_DICOM_ROOT}"
echo "Engines: ${ENGINES[*]}"
echo

for engine in "${ENGINES[@]}"; do
  safe_engine="${engine//-/_}"
  for morph_label in morph_on morph_off; do
    morph_args=()
    out_suffix="${safe_engine}_${morph_label}"
    if [[ "${morph_label}" == "morph_off" ]]; then
      morph_args=(--matrix-no-morph-close)
    fi
    out_dir="${RUN_ROOT}/${out_suffix}"
    echo "=== ${engine} | ${morph_label} -> ${out_dir} ==="
    "${PY[@]}" -m app.tools.batch.sweep_preprocessing_headless \
      "${common_args[@]}" \
      "${morph_args[@]}" \
      --engine "${engine}" \
      --output-dir "${out_dir}"
  done
done

echo
echo "Done. Summaries: ${RUN_ROOT}/*/summary.csv"
