# OCR Engine Comparison

Total runtime: 690.2s

## Label Set: labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 31 | 100.0% | 100.0% | 100.0% | 1.3% | 0.0% | 9.9 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 31 | 29 | 73.1% | 91.0% | 80.8% | 71 | 9.1 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 31 | 31 | 80.8% | 96.2% | 82.1% | 79 | 143.1 |

## Label Set: validation_labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 77 | 100.0% | 100.0% | 97.7% | 0.9% | 0.0% | 28.7 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 77 | 66 | 56.8% | 82.2% | 65.3% | 179 | 28.7 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| paddleocr | 77 | 76 | 69.0% | 95.8% | 70.9% | 262 | 468.4 |
