#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v mamba >/dev/null 2>&1; then
  echo "mamba is required but not found in PATH."
  exit 1
fi

echo "Using project root: $ROOT_DIR"

envs=(
  "envs/dl.yml"
  "envs/glm_ocr.yml"
  "envs/surya.yml"
)

for env_file in "${envs[@]}"; do
  echo "Ensuring environment from $env_file"
  mamba env create -f "$env_file" || mamba env update -f "$env_file" --prune
  echo "Done: $env_file"
done

echo "Running smoke checks"
mamba run -n DL python -c "import sys; print('DL python:', sys.version.split()[0])"
mamba run -n DL python -m app.tools.headless_batch_label --help >/dev/null
mamba run -n glm_ocr python -c "import transformers; print('glm_ocr transformers ok')"
mamba run -n surya python -c "import surya; print('surya import ok')"

echo "Bootstrap complete."
