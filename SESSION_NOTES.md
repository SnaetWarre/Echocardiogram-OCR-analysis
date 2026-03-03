# OCR Research Session Notes — 2026-03-02

## 🎯 Goal
Find the best possible OCR method for extracting echocardiography measurements from DICOM overlay text. Target: as close to 100% accuracy as possible.

## 📊 Benchmark Results

The evaluation tool is `app/tools/echo_ocr_eval_labels.py`. It tests against **78 ground-truth labels** across **31 DICOM files** from a single patient study.

| Engine | Value Match | Full Match | Speed | Notes |
|--------|-------------|------------|-------|-------|
| EasyOCR + regex | 91.0% (71/78) | ~83% | ~50s | Baseline after OpenCV morphological enhancements |
| **Surya OCR** | **91.0% (71/78)** | **83.3% (65/78)** | **~51s** | Best current, same as EasyOCR |
| GOT-OCR 2.0 (raw) | 26.9% (21/78) | 10.3% (8/78) | ~52s | Splits/fuses compound abbreviations |
| GOT-OCR 2.0 + Normalizer | 76.9% (60/78) | 73.1% (57/78) | ~52s | Massive 7× lift, but still loses to Surya |

## 🔬 Key Observations

### Why Surya = 91%
- Surya OCR is a document-specific VLM and handles the dense text very well
- Still misses measurements when the text box is too dark/small or values have unusual decimal formatting
- Ties on full-match with EasyOCR — both fail on similar fringe cases

### Why GOT-OCR 2.0 = 76.9% value / 73.1% full
- **Initial finding**: Without normalisation, GOT-OCR scores only 10.3% full match because it outputs all tokens on a single line and frequently splits/fuses medical abbreviations (`AVVmax`, `L VED V`).
- **After normalisation**: We built `app/pipeline/gotocr_normalizer.py` with 30+ regex rules to fix splits, fuses, and line breaks.
- **The result**: the normaliser lifted full matches by 7× (10% → 73%).
- **Conclusion**: Even heavily normalised, GOT-OCR (76.9% value match) performs slightly worse than Surya OCR (91.0%). The root issue isn't just whitespace; GOT-OCR sometimes misreads tiny characters or drops whole measurements when boxes are cluttered. Surya remains the superior engine for this dense medical layout.

### Shared weaknesses across all engines
- Measurements printed very small (e.g. `IVC 2.2 cm`, `RVIDd 3.2 cm`) — only 1 label each, text is tiny
- Labels prefixed with frame overlays like `1 I VC 2.2 cm` — frame number interferes with name parsing
- Abbreviations containing subscripts (`m²`, `ml/m²`) lose formatting in plain text

## 🏗️ Infrastructure Built Today

### New mamba environments
- `surya` — Surya OCR engine (isolated from DL env due to PyTorch VRAM conflicts)
- `gotocr` — GOT-OCR 2.0 with PyTorch CUDA 12.1, HuggingFace transformers 5.x

### New evaluation tools
- `app/tools/eval_surya.py` — Cross-env bridge for Surya OCR evaluation
- `app/tools/eval_gotocr.py` — Cross-env bridge for GOT-OCR 2.0 evaluation
- Both use a **single-subprocess batch pattern** to avoid CUDA VRAM leaks from re-initializing the model on every image

## 🔮 Next Steps (Tomorrow)

### ❌ Option A — Normalize GOT-OCR output (COMPLETED)
- Built `gotocr_normalizer.py` and achieved a massive 7× lift in full match accuracy (from 10% → 73%).
- However, Surya OCR is still more accurate (83% full / 91% value).

### ✅ Option B — Integrate Surya into main pipeline (NEXT)
- Replace `EasyOcrEngine` with a `SuryaOcrEngine` in the main application pipeline.
# Pseudocode
def normalize_ocr_text(text: str) -> str:
    # Merge known split acronyms back
    text = re.sub(r'\b([A-Z]{1,4})\s([A-Z])\s', r'\1\2 ', text)
    ...
```

### Option B — Integrate Surya into main pipeline
- Replace `EasyOcrEngine` with a `SuryaOcrEngine` in the main application pipeline
- Run Surya as a persistent long-lived subprocess to avoid model reload overhead
- Architecture: `app/pipeline/ocr_engines.py` → add `SuryaOcrEngine` class

### Option C — Ensemble voting
- Run both Surya and GOT-OCR, pick the prediction with higher confidence or use majority vote
- More complex but theoretically achieves highest accuracy

### Notes
- GOT-OCR 2.0 weights are cached at `~/.cache/huggingface/hub/`
- Surya weights are cached in the `surya` mamba env's site-packages
- The `DL` environment remains the main app environment; OCR engines run as subprocesses

## 📁 Files Changed Today
- `app/tools/eval_surya.py` — NEW: Surya OCR benchmark bridge
- `app/tools/eval_gotocr.py` — NEW: GOT-OCR 2.0 benchmark bridge
- `app/tools/echo_ocr_eval_labels.py` — NEW: Full evaluation framework
- `app/ui/components/` — NEW: Refactored UI component directory
- `app/ui/state.py` — NEW: Centralized UI state management
- `pyproject.toml` — NEW: Python project config with ruff/mypy
- Various `app/pipeline/` and `app/io/` — Refactored and improved
