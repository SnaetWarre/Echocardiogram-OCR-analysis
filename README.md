# DICOM Viewer Repo Map

This repository contains a PySide6 DICOM viewer, an OCR pipeline for echo measurement panels, and a set of developer tools for validation, evaluation, and recognizer experiments.

## Start Here

- GUI entrypoint: `app/main.py`
- Main window and UI orchestration: `app/ui/`
- DICOM loading and normalization: `app/io/`
- OCR pipeline and model integration: `app/pipeline/`
- Shared validation and dataset logic: `app/validation/`
- OCR preprocessing helpers: `app/ocr/`
- Runtime startup and GUI pipeline presets: `app/runtime/`
- Measurement parsing and decoding entrypoints: `app/measurement/`
- CLI and developer tools: `app/tools/`
- Tests: `tests/`

## Repo Layout

### Runtime App

- `app/main.py`: launches the desktop app and startup services.
- `app/ui/`: windows, dialogs, widgets, Qt state objects, and workers.
- `app/io/`: DICOM readers, lazy frame loading, metadata extraction, and normalization.
- `app/pipeline/`: core OCR orchestration, engines, segmentation, transcription, and validation-adjacent helpers.

### Domain Packages

- `app/validation/`: canonical label dataset loading, evaluation helpers, validation queue building, and label writing.
- `app/runtime/`: startup/service management plus GUI OCR manager presets.
- `app/ocr/`: OCR-specific preprocessing helpers that should not live inside UI code.
- `app/measurement/`: measurement parser and decoder entrypoints grouped in one place for discoverability.

### Tooling

- `app/tools/eval/echo_ocr_eval_labels.py`: CLI wrapper for exact-line evaluation.
- `app/tools/batch/headless_batch_label.py`: headless batch DICOM processing with aggregate JSON/CSV export.
- `app/tools/eval/eval_line_transcription.py`: line-first evaluation and hard-case reporting.
- `app/tools/artifacts/build_ocr_lexicon.py`: lexicon/statistics artifact generation.
- `app/tools/prepare_line_training_data.py`: JSONL export for exact-line training rows.
- `app/tools/prepare_line_recognizer_dataset.py`: crop + manifest export for recognizer experiments.
- `app/tools/train_line_recognizer.py`: recognizer training run skeleton.
- `app/tools/char_fallback_dataset_bootstrap.py`: build char-level train/val manifests from mismatch artifacts.
- `app/tools/char_fallback_labeled_roi_bootstrap.py`: same manifests, but crops come from **real DICOM line ROIs** (mismatches in `label_scores.json` + `labels/labels.json` paths), not `putText` renders.
- `app/tools/train_char_fallback_model.py`: compact CNN training/export for char fallback artifacts.
- `app/tools/eval/eval_char_fallback_rollout.py`: compare baseline vs fallback label score outputs.
- `app/tools/eval/eval_segmentation.py`: segmentation benchmark entrypoint.

CLI entrypoints live under `app/tools/`; run them with `python -m app.tools.<module>`.

## Data And Artifacts

- Curated source labels live in `labels/exact_lines.json`.
- Human-authored docs live in `docs/`.
- Generated OCR redesign outputs now belong in `artifacts/ocr_redesign/`.
- Runtime logs belong in `logs/`.

Use these defaults when adding or updating scripts:

- labels: `labels/exact_lines.json`
- lexicon: `artifacts/ocr_redesign/exact_lines_lexicon.json`
- line training data: `artifacts/ocr_redesign/line_training_data.jsonl`
- recognizer manifest: `artifacts/ocr_redesign/line_recognizer_manifest.jsonl`
- recognizer crops: `artifacts/ocr_redesign/line_recognizer_crops/`
- recognizer training output: `artifacts/ocr_redesign/line_recognizer_training/`
- char fallback model output: `artifacts/ocr_redesign/char_model/`
- OCR redesign run log: `artifacts/ocr_redesign/run_log.jsonl`

## Common Commands

Create the primary app environment with `mamba env create -f envs/dl.yml`.
See `docs/mamba_environments.md` for the full multi-environment setup.

```bash
mamba run -n DL python -m app.main
mamba run -n DL python -m pytest
mamba run -n DL python -m app.tools.eval.echo_ocr_eval_labels --split validation --engine surya
mamba run -n DL python -m app.tools.eval.eval_line_transcription --split validation
mamba run -n DL python -m app.tools.char_fallback_dataset_bootstrap --label-scores artifacts/ocr_redesign/my_sweep/gray_x3_lanczos/label_scores.json --validation-exact-failures-csv artifacts/ocr_redesign/my_sweep/validation_exact_failures.csv --output-dir artifacts/ocr_redesign/char_bootstrap --merge-scan-dir artifacts/ocr_redesign --merge-scan-limit 64 --real-augment-copies 8 --synthetic-rounds 2
mamba run -n DL pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
mamba run -n DL python -m app.tools.train_char_fallback_model --dataset-dir artifacts/ocr_redesign/char_bootstrap --output-root artifacts/ocr_redesign/char_model --device auto --cnn-variant large --no-early-stop --epochs 200
mamba run -n DL python -m app.tools.artifacts.build_ocr_lexicon
mamba run -n DL python -m app.tools.batch.headless_batch_label /path/to/dicoms --recursive --output artifacts/ocr_redesign/headless_run --output-format json
mamba run -n DL python -m app.tools.batch.headless_batch_label /path/to/dicoms --recursive --output artifacts/ocr_redesign/headless_run --output-format both --resume
```

## Notes

- Prefer `app.runtime.*` and `app.validation.*` for GUI presets and label I/O instead of duplicate re-exports.
- If you are looking for label schema or evaluation code, start in `app/validation/`, not `app/tools/`.
- If you are looking for OCR preprocessing, start in `app/ocr/preprocessing.py`.
