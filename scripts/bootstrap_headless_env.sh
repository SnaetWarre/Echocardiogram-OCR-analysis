#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_TOOL=""
if command -v mamba >/dev/null 2>&1; then
  ENV_TOOL="mamba"
elif command -v conda >/dev/null 2>&1; then
  ENV_TOOL="conda"
else
  echo "Neither mamba nor conda was found in PATH."
  exit 1
fi

echo "Using project root: $ROOT_DIR"
echo "Using environment tool: $ENV_TOOL"

envs=(
  "envs/dl.yml"
  "envs/glm_ocr.yml"
  "envs/surya.yml"
)

for env_file in "${envs[@]}"; do
  echo "Ensuring environment from $env_file"
  "$ENV_TOOL" env create -f "$env_file" || "$ENV_TOOL" env update -f "$env_file" --prune
  echo "Done: $env_file"
done

echo "Running smoke checks"
"$ENV_TOOL" run -n DL python -c "import sys; print('DL python:', sys.version.split()[0])"
"$ENV_TOOL" run -n DL python -m app.tools.headless_batch_label --help >/dev/null
"$ENV_TOOL" run -n glm_ocr python -c "import transformers; print('glm_ocr transformers ok')"
"$ENV_TOOL" run -n surya python -c "import surya; print('surya import ok')"

echo "Bootstrap complete."
