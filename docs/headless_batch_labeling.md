# Headless Batch Labeling

This command runs the Echo OCR pipeline on large DICOM batches without the GUI and writes one aggregate artifact per run.

## Quickstart

Use the main runtime environment:

```bash
mamba run -n DL python -m app.tools.headless_batch_label /path/to/dicoms --recursive --output artifacts/ocr_redesign/headless_run --output-format json
```

Dual export with resume:

```bash
mamba run -n DL python -m app.tools.headless_batch_label /path/to/dicoms --recursive --output artifacts/ocr_redesign/headless_run --output-format both --resume
```

Preflight-only startup validation:

```bash
mamba run -n DL python -m app.tools.headless_batch_label /path/to/dicoms --preflight --output artifacts/ocr_redesign/headless_preflight --output-format json
```

## Core Flags

- `input_path`: file or directory input.
- `--pattern`: glob for discovery, default `*.dcm`.
- `--recursive`: recurse for directory input.
- `--max-files`: optional cap for discovery.
- `--output-format`: `json`, `csv`, or `both`.
- `--output`: base output path.
- `--engine`: primary OCR engine, default `glm-ocr`.
- `--fallback-engine`: fallback OCR engine, default `surya`.
- `--strict-engine-selection`: disable permissive fallback chain.
- `--parser-mode`: parser mode passthrough.
- `--max-frames`: max frames per file.
- `--continue-on-error` / `--no-continue-on-error`: failure behavior.
- `--resume`: resume from checkpoint/output and skip already processed files.
- `--checkpoint-path`: explicit checkpoint file.
- `--checkpoint-interval`: save checkpoint every N processed files.
- `--run-id`, `--run-tag`, `--run-note`: run metadata.

## Output Artifacts

The command writes these files based on `--output-format`:

- `<output>.json`: aggregate JSON with run manifest and item-level records.
- `<output>.csv`: flattened measurement rows.
- `<output>.checkpoint.json`: resumable checkpoint.

### JSON shape

```json
{
  "manifest": {
    "run_id": "headless-...",
    "started_at": "...",
    "ended_at": "...",
    "elapsed_s": 12.3,
    "args": {"engine": "glm-ocr", "output_format": "json"},
    "resources": {"cpu_count": 16, "ram_gb": 31.2, "gpu_detected": true},
    "summary": {"total_discovered": 100, "processed": 100, "ok": 92, "error": 8, "skipped": 0}
  },
  "items": [
    {
      "dicom_path": "/data/sample.dcm",
      "status": "ok",
      "measurements": [{"name": "LVIDd", "value": "5.2", "unit": "cm", "source": "..."}],
      "metadata": {"model_name": "echo-ocr:...", "line_prediction_count": 8},
      "error": null
    }
  ]
}
```

## Operational Notes

- v1 intentionally runs single-process for deterministic behavior and stability.
- Files are processed in deterministic sorted order.
- `--resume` reads checkpoint/output and skips already processed file paths.
- With default `--continue-on-error`, failures are recorded per file and the run continues.

## Troubleshooting

- Missing `glm_ocr` environment: verify `mamba env list` and create from `envs/glm_ocr.yml`.
- Missing `surya` environment: verify and create from `envs/surya.yml`.
- Slow first-run startup: model initialization and cache download can take time.
- Invalid DICOM files are recorded as `status=error` in output, not dropped.
