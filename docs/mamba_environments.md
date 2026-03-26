# Mamba Environments

This repo now tracks its mamba environment specs in `envs/*.yml`.

Keep the environment names unchanged because the runtime defaults already look for them:

- `DL`
- `surya`
- `glm_ocr`
- `gotocr`
- `easyocr_eval`
- `paddleocr_eval`

## Standard Layout

- One YAML file per environment under `envs/`
- Lowercase YAML filenames
- Stable runtime environment names inside each file
- `conda-forge` as the shared channel
- `mamba run -n <env> ...` for commands instead of shell activation assumptions

## Create Environments

```bash
mamba env create -f envs/dl.yml
mamba env create -f envs/surya.yml
mamba env create -f envs/glm_ocr.yml
mamba env create -f envs/gotocr.yml
mamba env create -f envs/easyocr_eval.yml
mamba env create -f envs/paddleocr_eval.yml
```

## Update Existing Environments

```bash
mamba env update -f envs/dl.yml --prune
mamba env update -f envs/surya.yml --prune
mamba env update -f envs/glm_ocr.yml --prune
mamba env update -f envs/gotocr.yml --prune
mamba env update -f envs/easyocr_eval.yml --prune
mamba env update -f envs/paddleocr_eval.yml --prune
```

## Environment Roles

- `DL`: main app, tests, DICOM tooling, lightweight evaluation, and general CLI work
- `surya`: isolated Surya OCR worker environment
- `glm_ocr`: isolated GLM-OCR worker environment
- `gotocr`: isolated GOT-OCR evaluation environment
- `easyocr_eval`: isolated EasyOCR evaluation environment
- `paddleocr_eval`: isolated PaddleOCR evaluation environment

## Commands Used In This Redesign

- App: `mamba run -n DL python -m app.main`
- Tests: `mamba run -n DL python -m pytest ...`
- Lexicon build: `mamba run -n DL python -m app.tools.build_ocr_lexicon`
- Line evaluation: `mamba run -n DL python -m app.tools.eval_line_transcription ...`
- Recognizer dataset export: `mamba run -n DL python -m app.tools.prepare_line_recognizer_dataset ...`
- Recognizer training dry-run: `mamba run -n DL python -m app.tools.train_line_recognizer --dry-run ...`
- Surya worker auto-detects `mamba run -n surya` unless overridden
- GLM-OCR worker auto-detects `mamba run -n glm_ocr` unless overridden

## Notes

- **GLM-OCR model source**: the worker loads weights via Hugging Face (`zai-org/GLM-OCR` by default). The first run downloads into the Hub cache (typically `~/.cache/huggingface/hub`); later runs are read from disk unless you bump revisions. Override with a **local folder** (full model checkout) if you want no Hub id in code:
  ```bash
  export GLM_OCR_MODEL=/path/to/local/GLM-OCR-snapshot
  ```
  For air-gapped use after a one-time download: `export HF_HUB_OFFLINE=1` (and keep the cache).
- **GLM-OCR worker** (`glm_ocr`): if `AutoProcessor.from_pretrained` fails with `TypeError: argument of type 'NoneType' is not iterable` in `video_processing_auto.py`, install **torchvision** (transformers maps video processors to `None` without it). Fix:
  ```bash
  mamba run -n glm_ocr pip install torchvision==0.20.1
  ```
  Or refresh from the spec (now includes `torchvision`): `mamba env update -f envs/glm_ocr.yml --prune`
- **GLM-OCR `No module named 'transformers'` / “use the current Python”**: refresh the env: `mamba env update -f envs/glm_ocr.yml --prune`. The app looks for **mamba/conda on `PATH`**, then common installs (**`$CONDA_EXE`**, `~/miniforge3/bin`, `~/mambaforge/bin`, `/opt/conda/bin`, …) so GUI-spawned Jupyter still finds the runner. If everything fails, it falls back to the **notebook kernel** — install the `glm_ocr` pip stack there or set `GLM_OCR_RUNNER=python` only after doing so.
- `easyocr_eval` and `paddleocr_eval` pin `numpy<2` to avoid OpenCV wheel ABI mismatches
- Keep heavyweight OCR dependencies isolated when they conflict with UI/runtime packages
- Record all benchmark and evaluation runs in `artifacts/ocr_redesign/run_log.jsonl`
