# OCR Redesign Plan

## Goal

Redesign the echo OCR pipeline so it is driven by exact line transcription instead of hardcoded regex parsing.

The new system should:
- maximize OCR accuracy for echocardiography measurement overlays
- stay fully local/offline
- avoid hardcoding measurement-specific regex patterns
- scale to large datasets
- stay compatible with the current app and evaluation tooling where possible

---

## Core Direction

Stop treating this problem as:

`ROI -> OCR text blob -> regex parse`

and move to:

`ROI detect -> line segment -> per-line OCR -> candidate rerank -> generic structured decode`

The primary task is **exact displayed line transcription**, because that is already the ground truth format in `labels/exact_lines.json`.

Structured `(name, value, unit)` parsing becomes a **secondary derived step**, not the main source of truth.

---

## Why This Direction

The current pipeline relies too much on brittle cleanup logic:
- hardcoded regexes
- hardcoded label corrections
- hardcoded unit fixes
- whole-box OCR instead of line-level OCR
- fixed assumptions like static header trimming

That approach will keep breaking as new measurement labels appear.

The exact-line label dataset is a much better foundation:
- it captures what is actually shown on screen
- it preserves ordering
- it preserves prefixes
- it supports evaluation without guessing parser intent
- it can drive lexicon building, reranking, and future training

---

## Reality Check

True 100 percent accuracy on millions of images is not realistic.

Some images will always be ambiguous because of:
- tiny text
- compression artifacts
- motion blur
- aliasing
- clipping
- bad contrast
- overlay variations

The best practical target is:
- high exact-line accuracy on clean cases
- strong fallback behavior on hard cases
- explicit uncertainty/abstention instead of hallucinated output
- continuous improvement through evaluation and hard-case collection

---

## Target Architecture

### 1. ROI Detection
Keep the current measurement panel detector as the first path because it is already domain-aware and likely valuable.

Improve it by:
- supporting multiple candidate ROI boxes when confidence is weak
- adding a fallback if the blue-gray box heuristic fails
- replacing the fixed `14px` header trim with dynamic header detection
- storing ROI confidence and candidate metadata for analysis

### 2. Line Segmentation
Do not OCR the whole ROI as one text blob.

Instead:
- split the ROI into individual text lines
- use OCR token boxes when available
- otherwise use horizontal projection / connected-component based segmentation
- preserve line order explicitly
- allow merging only when evidence suggests a split OCR line belongs together

### 3. Per-Line OCR
Run OCR on each segmented line independently.

Design:
- primary local OCR engine for all lines
- secondary local OCR engine only for uncertain lines
- optional multi-view preprocessing only for uncertain lines
- keep raw candidates and confidences, not just the chosen string

### 4. Candidate Reranking
Replace hardcoded measurement regex logic with a data-driven reranker.

Reranking signals:
- OCR confidence
- engine agreement
- edit distance to known label families
- valid unit likelihood
- numeric plausibility
- prefix consistency
- order consistency inside a panel
- similarity to exact labeled lines and token patterns

This is still general and extensible, not hardcoded per measurement label.

### 5. Generic Structured Decode
After selecting the best exact line, decode it into:
- optional prefix
- free-form label
- numeric value
- optional unit

This decoder should stay generic:
- no measurement-specific regex tables
- only minimal syntax-aware extraction
- preserve unknown labels safely
- validate numbers and units conservatively

### 6. Confidence Routing and Abstention
If a line remains uncertain:
- mark it uncertain
- avoid inventing a confident parse
- surface uncertainty for validation and future learning

---

## Proposed Repo Changes

### Keep
- current pipeline shell and output model
- current exact-line evaluation dataset
- current sidecar writing flow
- current box detector as first-pass ROI detection
- existing OCR engine abstraction

### Replace or Reduce
- regex-first parsing strategy
- large hardcoded cleanup tables
- whole-box OCR as the main strategy
- fixed header trimming
- parser logic that assumes known label patterns

### Add
New modules likely needed:
- `app/pipeline/line_segmenter.py`
- `app/pipeline/line_transcriber.py`
- `app/pipeline/lexicon_builder.py`
- `app/pipeline/lexicon_reranker.py`
- `app/pipeline/measurement_decoder.py`
- `app/tools/build_ocr_lexicon.py`
- `app/tools/eval_line_transcription.py`

---

## Phased Implementation Plan

### Phase 1 - Make Exact-Line OCR the Center
Objective:
- make exact-line transcription the main internal target

Tasks:
- audit current pipeline outputs and separate transcription from structured parsing
- add a lexicon/statistics builder from `labels/exact_lines.json`
- define a canonical in-memory line prediction object
- update evaluation emphasis toward exact-line accuracy
- keep current parser as fallback only

Deliverables:
- reusable label lexicon
- line prediction abstraction
- updated evaluation metrics
- no new hardcoded measurement regexes

### Phase 2 - Add Line Segmentation
Objective:
- stop OCRing the full ROI as one block

Tasks:
- segment ROI into candidate lines
- preserve line ordering
- benchmark segmentation quality against validation data
- support merged/split line recovery at the segmentation layer, not in measurement regexes

Deliverables:
- `line_segmenter.py`
- per-line crops
- debug artifacts for segmentation inspection

### Phase 3 - Add Multi-Engine Local OCR Routing
Objective:
- improve difficult cases without paying full cost on every image

Tasks:
- choose a primary engine and a fallback engine
- run primary OCR on all lines
- route low-confidence lines to fallback OCR
- compare candidates and retain confidence metadata
- expose engine-level debug output

Recommended default:
- primary: `surya` or `paddleocr`
- fallback: the other one
- optional future third path for experimentation only

Deliverables:
- line-level multi-engine OCR orchestration
- routing thresholds
- engine comparison reports

### Phase 4 - Add Data-Driven Reranking
Objective:
- improve accuracy without hardcoding label regex patterns

Tasks:
- build token and label-family statistics from exact-line labels
- rank OCR candidates using lexicon similarity and syntax plausibility
- preserve unseen labels instead of forcing them into known forms
- design reranking so new labels can be absorbed automatically from data

Deliverables:
- `lexicon_builder.py`
- `lexicon_reranker.py`
- offline benchmark improvements over raw OCR

### Phase 5 - Generic Structured Decode
Objective:
- derive structured measurements from the chosen exact line

Tasks:
- decode prefix, label, value, and unit generically
- keep unknown labels intact
- validate units and number format conservatively
- remove measurement-specific correction tables where possible

Deliverables:
- `measurement_decoder.py`
- smaller and cleaner parser layer
- structured outputs still compatible with the UI/pipeline

### Phase 6 - Training/Fine-Tuning Path
Objective:
- unlock the next big accuracy gain if rule-free inference alone is not enough

Tasks:
- prepare line-level training examples from exact-line labels
- later extend labels with `frame_index` and optionally line boxes
- create synthetic overlays matching the ultrasound text style
- fine-tune a local line recognizer on domain data
- evaluate before replacing the default inference path

Important:
- do **not** start with custom training
- first get the pipeline architecture right
- then add training if the validation plateau remains too low

Deliverables:
- reproducible training dataset prep
- synthetic data generation plan
- fine-tuning experiment path

---

## Evaluation Strategy

Primary metrics:
- exact line match rate
- label match rate
- value match rate
- unit match rate
- prefix match rate

Additional production metrics:
- uncertainty/abstention rate
- fallback engine invocation rate
- ROI detection failure rate
- line segmentation failure rate
- disagreement rate between OCR engines
- average processing time per file

Error buckets:
- ROI missed
- ROI cropped poorly
- header removal error
- line segmentation error
- OCR recognition error
- reranker chose wrong candidate
- decoder failed on valid line
- ground-truth ambiguity / possible label noise

---

## Label Dataset Improvements Later

Current labels are already useful, but later improvements should include:
- `frame_index`
- optional per-line bounding boxes
- annotation confidence / review status
- richer split usage (`train`, `validation`, `test`)
- hard-case tags

This is not required for the first redesign pass.

---

## Environment and Tooling

Use `mamba` for environment management.

Requirements:
- all OCR-related environments should be documented with `mamba`
- separate environments are acceptable for heavyweight engines if needed
- environment setup commands should prefer `mamba create` / `mamba env create`
- evaluation and benchmarking tools should document which `mamba` environment they run in
- avoid undocumented mixed environment assumptions

Suggested direction:
- one main app environment
- optional dedicated OCR environments only if a model has conflicting dependencies
- document exact commands in the final implementation notes

---

## Success Criteria

The redesign is successful if it achieves most of the following:
- exact-line transcription becomes the primary pipeline output
- fewer hardcoded measurement regexes are needed
- new labels can appear without code changes
- value accuracy improves or stays high
- exact-line accuracy improves materially on the validation set
- low-confidence cases are surfaced honestly instead of hallucinated
- evaluation is easier to interpret by failure stage
- local-only workflow remains fully supported

---

## Immediate First Execution Steps

1. Create a new line-first prediction abstraction.
2. Build a lexicon/statistics artifact from `labels/exact_lines.json`.
3. Add line segmentation to the ROI path.
4. Add per-line OCR using the current engine abstraction.
5. Add a candidate reranker based on confidence plus dataset-driven similarity.
6. Keep the current parser as temporary fallback.
7. Re-run exact-line evaluation and compare against the current baseline.
8. Only then start removing old regex-heavy logic.

---

## Final Principle

This project should optimize for:

**read exactly what is on the image first**
and only then
**derive structure from that text**

That is the most robust path for new labels, fewer brittle rules, and higher long-term accuracy.
