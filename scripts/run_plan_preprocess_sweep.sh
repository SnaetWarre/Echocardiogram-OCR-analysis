#!/usr/bin/env bash
# Fixed 8-config sweep: bin/up/order ablation + 3× Lanczos vs cubic (names: plan_no_binarize_*,
# plan_scale_then_otsu_*, plan_otsu_then_scale_*; see _order_matrix_plan_configs).
#
# Same env vars as run_full_preprocess_sweep.sh; only the config grid is smaller.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUNNER=(mamba)
if ! command -v mamba >/dev/null 2>&1; then RUNNER=(conda); fi
MAMBA_ENV="${SWEEP_MAMBA_ENV:-DL}"
PY=("${RUNNER[@]}" "run" "-n" "${MAMBA_ENV}" "python")

: "${SWEEP_DICOM_ROOT:=}"
if [[ -z "${SWEEP_DICOM_ROOT}" ]]; then
  echo "Set SWEEP_DICOM_ROOT to your DICOM tree or single .dcm"
  exit 2
fi

OUT_PARENT="${SWEEP_OUTPUT_PARENT:-${ROOT_DIR}/artifacts/ocr_redesign}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT_PARENT}/plan_order_matrix_${STAMP}"
mkdir -p "${OUT}"

EXTRA=()
[[ -n "${SWEEP_EXTRA:-}" ]] && read -r -a EXTRA <<< "${SWEEP_EXTRA}"

ENGINE="${SWEEP_ENGINE:-glm-ocr}"

"${PY[@]}" -m app.tools.sweep_preprocessing_headless \
  "${SWEEP_DICOM_ROOT}" \
  --recursive \
  --config-set order_matrix_plan \
  --engine "${ENGINE}" \
  --split validation \
  --output-dir "${OUT}" \
  --resume-configs \
  --skip-existing \
  "${EXTRA[@]}"

echo "Summary: ${OUT}/summary.csv"
