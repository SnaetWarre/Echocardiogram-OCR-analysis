# OCR Engine Comparison

Total runtime: 762.7s

## Label Set: labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 100.0% | 100.0% | 100.0% | 39.7% | 38.5% | 20.4 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 29 | 76.9% | 84.6% | 83.3% | 75 | 17.9 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 31 | 31 | 87.2% | 97.4% | 88.5% | 81 | 152.5 |

## Label Set: validation_labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/validation_labels.md`

### Without Parser (raw OCR text)

| Engine | Files | Box Detect | OCR Text | Value Hit | Name+Value Hit | Full Hit | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 77 | 100.0% | 100.0% | 97.2% | 32.9% | 31.9% | 52.1 |

### With Regex Parser

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 77 | 72 | 63.4% | 76.5% | 70.4% | 185 | 50.7 |

### With Local LLM Parser (Qwen 2.5)

| Engine | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| surya | 77 | 77 | 80.3% | 93.9% | 82.2% | 260 | 459.6 |
