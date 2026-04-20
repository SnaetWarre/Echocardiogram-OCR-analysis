# OCR Engine Comparison

_All evaluations in this report use the strict measurement ROI detector (color-thresholded box selection), not the former broad top-left heuristic._

Total runtime: 650.1s

## Label Set: labels

Source: `labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 100.0% | 100.0% | 100.0% | 39.7% | 38.5% | 18.9 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 30 | 57.7% | 69.2% | 64.1% | 57 | 16.6 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 31 | 84.6% | 96.2% | 87.2% | 77 | 133.2 |

## Label Set: validation_labels

Source: `validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 98.7% | 98.7% | 93.9% | 33.6% | 33.2% | 44.7 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 73 | 55.1% | 68.7% | 62.6% | 154 | 42.0 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 72 | 77.6% | 86.9% | 79.9% | 191 | 349.3 |
