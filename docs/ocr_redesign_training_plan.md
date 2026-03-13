# OCR Redesign Training Path

## Goal

Prepare a reproducible next-step path for local line recognizer training without changing the current inference default.

## Dataset Prep

- Source labels from `labels/exact_lines.json`
- Generate line-level examples with `python -m app.tools.prepare_line_training_data`
- Keep the source dataset immutable; derived artifacts go under `docs/ocr_redesign/` or `logs/`
- Future dataset upgrades should add `frame_index`, optional per-line boxes, review status, and hard-case tags

## Synthetic Overlay Plan

- Render exact lines in ultrasound-like compact fonts on blue-gray measurement panels
- Randomize blur, aliasing, contrast, compression, clipping, and line spacing
- Mix synthetic prefixes, units, and unseen labels to improve open-vocabulary robustness
- Keep synthetic generation fully local/offline

## Fine-Tuning Experiments

- Start with line recognizer fine-tuning only after rule-free inference plateaus
- Compare against the current line-first pipeline on exact-line match rate first
- Use the existing `app/tools/eval_line_transcription.py` metrics as the acceptance gate
- Promote a trained model only if it clearly improves exact-line accuracy without raising hallucination risk

## Reproducibility

- Training artifacts should record source label hash, split filter, generated example count, and command line
- Keep evaluation outputs JSON-based for longitudinal comparison
- Do not replace the default OCR path until experiments beat the current local baseline
