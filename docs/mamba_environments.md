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

- `easyocr_eval` and `paddleocr_eval` pin `numpy<2` to avoid OpenCV wheel ABI mismatches
- Keep heavyweight OCR dependencies isolated when they conflict with UI/runtime packages
- Record all benchmark and evaluation runs in `artifacts/ocr_redesign/run_log.jsonl`
