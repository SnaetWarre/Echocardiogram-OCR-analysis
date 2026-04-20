# OCR Engine Comparison

_All evaluations in this report use the strict measurement ROI detector (color-thresholded box selection), not the former broad top-left heuristic._

Total runtime: 659.0s

## Label Set: labels

Source: `labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 100.0% | 100.0% | 98.7% | 41.0% | 38.5% | 17.8 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 29 | 82.1% | 92.3% | 88.5% | 72 | 15.9 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 31 | 87.2% | 96.2% | 87.2% | 78 | 140.4 |

## Label Set: validation_labels

Source: `validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 98.7% | 98.7% | 93.9% | 35.0% | 34.1% | 44.1 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 74 | 70.6% | 84.1% | 77.1% | 180 | 41.1 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 75 | 77.1% | 85.5% | 78.5% | 186 | 355.3 |
