# Echo OCR Scale Execution Plan

## Execution Model

- Run processing in resumable batches from a DICOM root directory.
- Persist progress state in `state.json` after each file.
- Retry each failed file up to `N` times before marking failed.

## Reliability Controls

- Persist success set (`done`) and failure map (`failed`) in state.
- Write per-file failure artifacts to a dedicated folder.
- Keep sidecar output deterministic per study key.

## Suggested Batch Procedure

1. Dry-run on 50 files.
2. Evaluate failure artifacts and tune detector/OCR thresholds.
3. Run on full bootstrap set (about 600 files).
4. Promote to larger production chunks (for example 10k files/job).

## Artifacts

- Sidecar outputs:
  - `*.measurements.jsonl`
  - `*.measurements.csv`
- Runtime state:
  - `artifacts/echo-ocr/state.json`
- Failure diagnostics:
  - `artifacts/echo-ocr/failures/*.failure.json`

## Operations Notes

- Rerunning the batch command resumes from `state.json`.
- Use `--max-files` for controlled test runs.
- Increase `--retries` when storage/network jitter affects reads.
