# OCR Engine Comparison

_All evaluations in this report use the strict measurement ROI detector (color-thresholded box selection), not the former broad top-left heuristic._

Total runtime: 638.6s

## Label Set: labels

Source: `labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 100.0% | 100.0% | 98.7% | 41.0% | 38.5% | 18.0 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 29 | 62.8% | 73.1% | 70.5% | 60 | 15.5 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 31 | 89.7% | 96.2% | 89.7% | 78 | 130.1 |

## Label Set: validation_labels

Source: `validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 98.7% | 98.7% | 93.9% | 35.0% | 34.1% | 45.0 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 73 | 55.1% | 69.2% | 62.6% | 155 | 41.0 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 78 | 74 | 78.5% | 87.9% | 81.8% | 195 | 343.8 |
