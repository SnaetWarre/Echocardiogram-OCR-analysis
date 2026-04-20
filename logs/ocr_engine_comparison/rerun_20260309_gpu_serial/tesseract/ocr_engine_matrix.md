# OCR Engine Comparison

Total runtime: 613.5s

## Label Set: labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 31 | 100.0% | 100.0% | 92.3% | 1.3% | 0.0% | 9.8 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 31 | 29 | 59.0% | 73.1% | 66.7% | 134 | 10.2 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 31 | 29 | 57.7% | 91.0% | 62.8% | 77 | 119.2 |

## Label Set: validation_labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 77 | 100.0% | 100.0% | 88.3% | 0.5% | 0.0% | 25.5 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 77 | 75 | 56.3% | 78.4% | 66.2% | 422 | 25.3 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 77 | 74 | 58.7% | 84.0% | 69.0% | 236 | 423.3 |
