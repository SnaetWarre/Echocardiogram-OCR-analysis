from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.types import AiMeasurement, AiResult, PipelineResult
from app.tools.batch import headless_batch_label


class _FakePipeline:
    def __init__(self, failing_name: str = "") -> None:
        self.failing_name = failing_name
        self.calls: list[str] = []

    def run(self, request: Any) -> PipelineResult:
        path = Path(request.dicom_path)
        self.calls.append(str(path))
        if self.failing_name and path.name == self.failing_name:
            return PipelineResult(dicom_path=path, status="error", ai_result=None, error="simulated failure")

        ai_result = AiResult(
            model_name="echo-ocr:test",
            created_at=datetime.now(timezone.utc),
            measurements=[
                AiMeasurement(name="LVIDd", value="5.2", unit="cm", source="exact_line:LVIDd 5.2 cm:1.0")
            ],
            raw={
                "record_count": 1,
                "source_kinds": ["pixel_ocr"],
                "parser_sources": ["line_first"],
                "line_predictions": [{"text": "LVIDd 5.2 cm"}],
                "ocr_benchmark": {"frame_count": 1},
            },
        )
        return PipelineResult(dicom_path=path, status="ok", ai_result=ai_result, error=None)


def _args(tmp_path: Path, **overrides: Any) -> Namespace:
    base = {
        "input_path": tmp_path,
        "pattern": "*.dcm",
        "recursive": True,
        "max_files": 0,
        "output": tmp_path / "results",
        "output_format": "json",
        "engine": "glm-ocr",
        "fallback_engine": "surya",
        "strict_engine_selection": False,
        "parser_mode": "off",
        "max_frames": 0,
        "continue_on_error": True,
        "resume": False,
        "checkpoint_path": None,
        "checkpoint_interval": 1,
        "preflight": False,
        "run_id": "",
        "run_tag": "",
        "run_note": "",
    }
    base.update(overrides)
    return Namespace(**base)


def test_discover_files_sorted_recursive(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "b" / "2.dcm").write_bytes(b"x")
    (tmp_path / "a" / "1.dcm").write_bytes(b"x")

    files = headless_batch_label.discover_files(tmp_path, "*.dcm", recursive=True)

    assert [path.name for path in files] == ["1.dcm", "2.dcm"]


def test_parser_defaults_output_json(tmp_path: Path) -> None:
    parser = headless_batch_label.build_parser()
    args = parser.parse_args([str(tmp_path)])

    assert args.output_format == "json"
    assert args.engine == "glm-ocr"
    assert args.continue_on_error is True


def test_output_format_both_writes_json_and_csv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "case1.dcm").write_bytes(b"x")

    fake = _FakePipeline()
    monkeypatch.setattr(headless_batch_label, "_build_pipeline", lambda _args: fake)

    exit_code = headless_batch_label.run_batch(_args(tmp_path, output_format="both"))

    assert exit_code == 0
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "results.csv").exists()


def test_continue_on_error_records_failure(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "ok.dcm").write_bytes(b"x")
    (tmp_path / "bad.dcm").write_bytes(b"x")

    fake = _FakePipeline(failing_name="bad.dcm")
    monkeypatch.setattr(headless_batch_label, "_build_pipeline", lambda _args: fake)

    exit_code = headless_batch_label.run_batch(_args(tmp_path, output_format="json"))

    assert exit_code == 0
    payload = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert '"status": "error"' in payload
    assert '"status": "ok"' in payload


def test_resume_skips_processed_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "one.dcm").write_bytes(b"x")
    (tmp_path / "two.dcm").write_bytes(b"x")

    checkpoint = tmp_path / "resume.checkpoint.json"
    checkpoint.write_text(
        '{"version":1,"items":[{"dicom_path":"'
        + str((tmp_path / "one.dcm").resolve())
        + '","status":"ok","measurements":[],"metadata":{},"error":null}]}',
        encoding="utf-8",
    )

    fake = _FakePipeline()
    monkeypatch.setattr(headless_batch_label, "_build_pipeline", lambda _args: fake)

    exit_code = headless_batch_label.run_batch(
        _args(tmp_path, output_format="json", resume=True, checkpoint_path=checkpoint)
    )

    assert exit_code == 0
    assert len(fake.calls) == 1
    assert Path(fake.calls[0]).name == "two.dcm"


def test_resume_filters_unrelated_checkpoint_items(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "one.dcm").write_bytes(b"x")
    unrelated = tmp_path.parent / f"{tmp_path.name}_outside.dcm"
    unrelated.write_bytes(b"x")

    checkpoint = tmp_path / "resume.checkpoint.json"
    checkpoint.write_text(
        '{"version":1,"items":[{"dicom_path":"'
        + str(unrelated.resolve())
        + '","status":"ok","measurements":[],"metadata":{},"error":null}]}',
        encoding="utf-8",
    )

    fake = _FakePipeline()
    monkeypatch.setattr(headless_batch_label, "_build_pipeline", lambda _args: fake)

    exit_code = headless_batch_label.run_batch(
        _args(tmp_path, output_format="json", resume=True, checkpoint_path=checkpoint)
    )

    assert exit_code == 0
    assert len(fake.calls) == 1
    payload = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert "outside.dcm" not in payload


def test_preflight_writes_report_and_exits(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "one.dcm").write_bytes(b"x")
    monkeypatch.setattr(
        headless_batch_label,
        "run_preflight",
        lambda engine, fallback_engine: {
            "checked_at": "2026-01-01T00:00:00+00:00",
            "engine": engine,
            "fallback_engine": fallback_engine,
            "checks": [{"name": "glm_ocr_worker", "status": "ok", "error": "", "elapsed_s": 0.1}],
            "ok": True,
        },
    )

    exit_code = headless_batch_label.run_batch(_args(tmp_path, preflight=True, output_format="json"))

    assert exit_code == 0
    report = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert '"checks"' in report
    assert '"ok": true' in report
