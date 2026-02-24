# Echo OCR Bootstrap Audit Protocol

## Purpose

Create a first manual ground-truth set from the 600 DICOM bootstrap subset to measure:
- measurement-box detection recall
- OCR readability
- parsing correctness

## Sampling Strategy

1. Build a frame manifest from all DICOM files.
2. Stratify by source file and frame index.
3. Sample:
   - 200 candidate positive frames (detector says box present)
   - 100 candidate negative frames (detector says no box)
4. Manually annotate:
   - `box_present` (yes/no)
   - `ocr_readable` (yes/no/partial)
   - extracted measurements as `name`, `value`, `unit`

## Annotation Rules

- Use exact on-image text for names where possible.
- Normalize decimal separators to `.` in the annotation file.
- Keep original units (`m/s`, `mmHg`, etc.).
- Mark uncertain characters with `?` and set `ocr_readable=partial`.

## Output Files

- `audit_manifest.csv`: sampled frames with traceability.
- `audit_annotations.csv`: human labels.
- `audit_joined.csv`: merged predicted vs labeled for metrics.

## Acceptance Targets (Bootstrap)

- Detector recall >= 0.95 on manually labeled positives.
- OCR readability >= 0.85 on true-positive boxes.
- Parser extraction success >= 0.80 on readable OCR text.
