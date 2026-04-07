cd /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/Master

export GLM_OCR_RUNNER=mamba
export GLM_OCR_ENV=glm_ocr   # adjust to your GLM env name if different

mamba run -n DL python -m app.tools.sweep_preprocessing_headless \
  /home/warre/Documents/howest/Semester_5/Stage/StageOpdracht/database_stage/files/p10/ \
  --recursive \
  --engine glm-ocr \
  --parser-mode off \
  --config-set broad \
  --labels labels/labels.json \
  --split validation \
  --only-configs gray_x3_lanczos \
  --output-dir artifacts/ocr_redesign/preprocess_sweep_glm_broad_v3



mamba run -n DL python -m app.tools.export_validation_failures \
  artifacts/ocr_redesign/preprocess_sweep_glm_broad_v3/gray_x3_lanczos/label_scores.json