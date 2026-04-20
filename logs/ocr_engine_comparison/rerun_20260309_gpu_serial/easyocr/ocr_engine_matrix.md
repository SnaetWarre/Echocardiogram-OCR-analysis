# OCR Engine Comparison

Total runtime: 1474.1s

## Label Set: labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 31 | 100.0% | 100.0% | 94.9% | 0.0% | 0.0% | 119.4 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 31 | 30 | 66.7% | 87.2% | 78.2% | 78 | 106.0 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 31 | 31 | 80.8% | 97.4% | 88.5% | 79 | 236.5 |

## Label Set: validation_labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 77 | 100.0% | 100.0% | 95.3% | 0.0% | 0.0% | 278.8 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 77 | 72 | 64.3% | 85.4% | 76.5% | 200 | 268.1 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| easyocr | 77 | 75 | 81.2% | 93.4% | 87.3% | 252 | 458.9 |
