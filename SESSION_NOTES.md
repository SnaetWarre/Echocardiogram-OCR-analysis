# OCR Research Session Notes — 2026-03-02

## 🎯 Goal
Find the best possible OCR method for extracting echocardiography measurements from DICOM overlay text. Target: as close to 100% accuracy as possible.

## 📊 Benchmark Results

The evaluation tool is `app/tools/echo_ocr_eval_labels.py`. It tests against **78 ground-truth labels** across **31 DICOM files** from a single patient study.

| Engine | Value Match | Full Match | Speed | Notes |
|--------|-------------|------------|-------|-------|
| EasyOCR + regex | 91.0% (71/78) | ~83% | ~50s | Baseline after OpenCV morphological enhancements |
| **Surya OCR** | **91.0% (71/78)** | **83.3% (65/78)** | **~51s** | Best current, same as EasyOCR |
| GOT-OCR 2.0 | 87.2% (68/78) | 33.3% (26/78) | ~52s | Splits compound abbreviations (`AV Vmax` → `AV V max`) |

## 🔬 Key Observations

### Why Surya = 91%
- Surya OCR is a document-specific VLM and handles the dense text very well
- Still misses measurements when the text box is too dark/small or values have unusual decimal formatting
- Ties on full-match with EasyOCR — both fail on similar fringe cases

### Why GOT-OCR 2.0 = 87.2% value / 33.3% full
- GOT-OCR reads values almost perfectly (87.2% value accuracy)
- **The core problem**: it inserts spaces inside compact medical abbreviations:
  - `AVVmax` → `AV V max` (then our regex can't match `AVVmax`)
  - `LAESV(A-L)` → `LAES V (A-L)`
  - `EF Biplane` → `EF Bi plane`
- **This is a normalizer problem, NOT an OCR problem**
- If we strip internal spaces from known abbreviations before matching, GOT-OCR accuracy would likely exceed Surya

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

### Option A — Normalize GOT-OCR output (Recommended 1st try)
Add a **medical abbreviation normalizer** post-processor that:
1. Removes unexpected internal spaces in multi-letter tokens (e.g. `LAES V` → `LAESV`)
2. Applies to GOT-OCR output before regex matching
3. Expected result: GOT-OCR full match likely jumps from 33% → 90%+

```python
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
