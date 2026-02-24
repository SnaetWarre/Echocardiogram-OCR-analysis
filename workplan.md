# Work Plan - Internship Project

## Background & Context

The project goal is to extract hard-burned measurement text from echocardiogram frames at scale. The source data contains multi-frame DICOM files, and only a subset of frames includes measurement overlays. These measurements are not available as DICOM metadata and must be read directly from pixels.

The expected production scale is around 500k images. A currently available subset of about 600 DICOM files will be used for prototyping and validation.

## Project Goal

Build a robust OCR pipeline that:
- detects whether a frame contains a measurement overlay box,
- localizes the blue/gray measurement box (typically top-left, variable position and size),
- extracts text and numerical measurements from that region,
- outputs structured sidecar files (JSONL/CSV) for frames with measurements.

## Scope Decisions (Confirmed)

- Input format: DICOM-first workflow.
- Frame reality: not all frames contain measurements.
- Box location prior: mostly top-left, but variable in size and exact position.
- Output for v1: sidecar files only.
- Output policy for v1: include only frames with detected/extracted measurements.
- Optimization priority: maximize recall (missing a true measurement frame is worse than a false positive).

## Technical Approach

### 1) DICOM Ingestion & Frame Extraction
- Read multi-frame DICOM studies.
- Extract pixel frames and preserve identifiers:
  - `study_uid`
  - `series_uid`
  - `sop_instance_uid`
  - `frame_index`

### 2) Measurement Presence Gate
- First decide whether a measurement box is present in each frame.
- Use a recall-oriented detector to avoid missing true measurement frames.
- Route frames without a detected box out of the OCR path.

### 3) ROI Detection (Measurement Box Localization)
- Detect the blue/gray overlay in the top-left region with tolerance for movement/size changes.
- Start with deterministic image rules (color, contrast, layout priors).
- Add fallback matching for style variation when needed.

### 4) OCR & Preprocessing
- Preprocess ROI crops (contrast normalization, denoise, scale-up).
- Benchmark OCR options on sample data and choose the best quality/speed tradeoff.
- Store raw OCR text and confidence values.

### 5) Parsing & Structuring
- Parse OCR output into structured fields:
  - `measurement_name`
  - `measurement_value`
  - `measurement_unit`
- Normalize decimal notation and units.
- Mark uncertain extractions with confidence metadata.

### 6) Sidecar Output
- Write sidecar records for frames with measurements:
  - primary: JSONL
  - optional: CSV export view
- Include traceability fields and processing metadata.

## Data Output Schema (v1)

Each output row/object should contain:
- `study_uid`
- `series_uid`
- `sop_instance_uid`
- `frame_index`
- `measurement_name`
- `measurement_value`
- `measurement_unit`
- `ocr_text_raw`
- `ocr_confidence`
- `parser_confidence`
- `roi_bbox`
- `processed_at`
- `pipeline_version`

## Validation Strategy

Because no labeled ground truth exists yet:
- Create a bootstrap audit set from the 600-file subset.
- Manually verify sampled outputs and detector misses.
- Track metrics per iteration:
  - measurement-box detection recall
  - OCR readability rate
  - parsing success rate
  - end-to-end extraction yield

## Scaling Strategy for 500k Images

- Run batched, resumable processing jobs.
- Log progress and failures per study/frame.
- Save debug artifacts for failed cases (ROI crop + OCR raw text).
- Add deduplication/hash checks to reduce repeated work.
- Use threshold tuning to keep recall high while limiting noise.

## Tentative Timeline (Approx. 3 Months)

### Month 1 - Feasibility & Setup
- Build DICOM frame extraction.
- Implement first measurement-presence gate and ROI detector.
- Benchmark OCR candidates on representative samples.
- Define output schema and logging format.

### Month 2 - Core Pipeline Development
- Integrate detection, OCR, parser, and sidecar writer into one pipeline.
- Add confidence scoring and failure logging.
- Run repeated evaluation on the 600-file subset and tune for recall.

### Month 3 - Scale, Validation & Finalization
- Harden pipeline for large-scale batch execution.
- Run larger dry-runs and analyze edge cases.
- Document methodology, metrics, and limitations.
- Prepare handoff artifacts and usage documentation.