# Mamba Environments

## Main App Environment

Use one primary environment for the app, tests, and lightweight evaluation:

```bash
mamba create -n DL python=3.11 pyside6 numpy pytest pillow opencv
```

## OCR-Specific Environments

Use dedicated environments only when dependencies conflict or models are heavy:

```bash
mamba create -n surya python=3.11 pillow numpy pytorch torchvision cpuonly
mamba create -n paddleocr_eval python=3.11 numpy paddleocr opencv
mamba create -n easyocr_eval python=3.11 numpy easyocr opencv
mamba create -n gotocr python=3.11 pillow transformers pytorch
```

## Commands Used In This Redesign

- Tests: `mamba run -n DL python -m pytest ...`
- Lexicon build: `mamba run -n DL python -m app.tools.build_ocr_lexicon`
- Line evaluation: `mamba run -n DL python -m app.tools.eval_line_transcription ...`
- Surya worker auto-detects `mamba run -n surya` unless overridden

## Notes

- Prefer `mamba run -n <env>` instead of undocumented shell activation assumptions
- Keep heavyweight OCR dependencies isolated when they conflict with UI/runtime packages
- Record all benchmark and evaluation runs in `docs/ocr_redesign_run_log.jsonl`
