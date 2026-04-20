# OCR Engine Comparison

Total runtime: 319.2s

## Label Set: labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/labels.md`

### Local LLM Only

| Model | Files | Files With Detections | Full Match | Value Match | Name Match | Predictions | Time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| granite3.2-vision:2b | 31 | 19 | 23.1% | 32.1% | 26.9% | 41 | 108.7 |

## Label Set: validation_labels

Source: `/home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master/validation_labels.md`

## Engine Errors

- validation_labels: granite3.2-vision:2b (local_vision_llm_only): timed out
