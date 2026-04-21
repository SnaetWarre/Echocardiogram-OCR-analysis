# Char Fallback Review Guide

This document explains how to read char-fallback fields emitted by headless sweep runs.

## Enable fallback

Set pipeline parameters:

- `char_fallback_enabled=true`
- `char_fallback_artifact_dir=artifacts/ocr_redesign/char_model`
- `char_fallback_min_split_confidence` (default `0.55`)
- `char_fallback_retry_confidence` (default `0.70`)
- `char_fallback_retry_min_char_confidence` (default `0.55`)
- `char_fallback_device` (default `cpu`)

Headless sweep equivalents:

- `--char-fallback-enabled`
- `--char-fallback-artifact-dir`
- `--char-fallback-min-split-confidence`
- `--char-fallback-retry-confidence`
- `--char-fallback-retry-min-char-confidence`
- `--char-fallback-device`

## Line-level fields

Each `line_predictions` entry may include:

- `manual_verify_required`: true when char retry was attempted.
- `fallback_trigger_reason`: why fallback policy fired (`low_quality`, `char_count_mismatch`, ...).
- `primary_text`: original selected OCR text before char retry.
- `char_retry_text`: retry candidate text from char classifier.
- `primary_quality`: quality score of primary candidate.
- `char_retry_confidence`: aggregate char retry confidence.
- `char_retry_min_char_confidence`: minimum confidence over retried characters.
- `char_count_expected`: split-derived expected character count.
- `char_count_predicted`: retry predicted count.

## Issues-only summary

Headless `issues_only.summary` reports:

- `fallback_invocations`
- `fallback_accepted_retries`
- `fallback_rejected_retries`
- `manual_verify_line_count`

`issues_only.manual_verify_rows` contains only retry-involved rows for fast review.
Each config now also writes:

- `manual_verify_rows.json`
- `manual_verify_rows.csv`

## Guardrail behavior

No silent override occurs:

- Retry replaces primary text only when retry confidence threshold and char-count consistency pass.
- Retry also requires per-character minimum confidence.
- Otherwise original text remains and `manual_verify_required=true`.
