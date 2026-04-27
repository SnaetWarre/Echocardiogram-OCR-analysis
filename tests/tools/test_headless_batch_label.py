from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.types import AiMeasurement, AiResult, PipelineResult
from app.tools.batch import headless_batch_label


class _FakePipeline:
    def __init__(
        self,
        failing_name: str = "",
        *,
        line_predictions: list[dict[str, Any]] | None = None,
        measurements: list[AiMeasurement] | None = None,
    ) -> None:
        self.failing_name = failing_name
        self.calls: list[str] = []
        self._line_predictions = line_predictions or [{"text": "LVIDd 5.2 cm"}]
        self._measurements = measurements or [
            AiMeasurement(name="LVIDd", value="5.2", unit="cm", source="exact_line:LVIDd 5.2 cm:1.0")
        ]

    def run(self, request: Any) -> PipelineResult:
        path = Path(request.dicom_path)
        self.calls.append(str(path))
        if self.failing_name and path.name == self.failing_name:
            return PipelineResult(dicom_path=path, status="error", ai_result=None, error="simulated failure")

        ai_result = AiResult(
            model_name="echo-ocr:test",
            created_at=datetime.now(timezone.utc),
            measurements=self._measurements,
            raw={
                "record_count": len(self._measurements),
                "source_kinds": ["pixel_ocr"],
                "parser_sources": ["line_first"],
                "line_predictions": self._line_predictions,
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
    payload = headless_batch_label.json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    patient_entry = next(iter(payload.values()))
    exam_entry = next(iter(patient_entry.values()))
    statuses = sorted(dicom["status"] for dicom in exam_entry["dicoms"])
    assert statuses == [1, 3]


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


def test_final_json_uses_root_patient_exam_map_and_plain_measurements(tmp_path: Path, monkeypatch) -> None:
    patient_dir = tmp_path / "patient_1" / "exam_1"
    patient_dir.mkdir(parents=True)
    (patient_dir / "case1.dcm").write_bytes(b"x")

    fake = _FakePipeline(
        line_predictions=[
            {"order": 1, "text": "1 IVSd 1.2 cm"},
            {"order": 2, "text": "LVIDd 4.7 cm"},
            {"order": 3, "text": "LVPWd 1.1 cm"},
        ],
        measurements=[
            AiMeasurement(name="IVSd", value="1.2", unit="cm"),
            AiMeasurement(name="LVIDd", value="4.7", unit="cm"),
            AiMeasurement(name="LVPWd", value="1.1", unit="cm"),
        ],
    )
    monkeypatch.setattr(headless_batch_label, "_build_pipeline", lambda _args: fake)

    exit_code = headless_batch_label.run_batch(_args(tmp_path, output_format="json"))

    assert exit_code == 0
    payload = headless_batch_label.json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert "predictions" not in payload
    dicom_entry = payload["patient_1"]["exam_1"]["dicoms"][0]
    assert dicom_entry["measurements"] == ["1 IVSd 1.2 cm", "LVIDd 4.7 cm", "LVPWd 1.1 cm"]
    assert dicom_entry["source"] == {"dicomid": None, "frame": None}
    assert dicom_entry["status"] == 3


def test_source_matcher_not_called_without_structured_measurements(tmp_path: Path, monkeypatch) -> None:
    path = (tmp_path / "patient_1" / "exam_1" / "case1.dcm").resolve()
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    items = [
        {
            "dicom_path": str(path),
            "status": "ok",
            "measurements": [],
            "line_predictions": [{"order": 1, "text": "LVIDd 5.2 cm"}],
            "metadata": {},
            "error": None,
        }
    ]
    calls: list[str] = []

    def _fake_matcher(*_args: object, **_kwargs: object) -> dict[str, object]:
        calls.append("called")
        return {"dicomid": str(path), "frame": 0, "matched": True}

    monkeypatch.setattr(headless_batch_label, "find_source_video_for_measurement_dicom", _fake_matcher)

    headless_batch_label._enrich_items_with_source_matches(items)

    assert calls == []
    assert items[0]["source"] == {"dicomid": None, "frame": None}


def test_source_matcher_called_for_measurement_positive_item(tmp_path: Path, monkeypatch) -> None:
    path = (tmp_path / "patient_1" / "exam_1" / "case1.dcm").resolve()
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    items = [
        {
            "dicom_path": str(path),
            "status": "ok",
            "measurements": [{"name": "LVIDd", "value": "5.2", "unit": "cm"}],
            "line_predictions": [{"order": 1, "text": "LVIDd 5.2 cm"}],
            "metadata": {},
            "error": None,
        }
    ]

    monkeypatch.setattr(
        headless_batch_label,
        "find_source_video_for_measurement_dicom",
        lambda *_args, **_kwargs: {
            "dicomid": "/tmp/video.dcm",
            "frame": 17,
            "matched": True,
            "score": 0.99,
            "mae": 0.01,
            "reason": "",
        },
    )

    headless_batch_label._enrich_items_with_source_matches(items)

    assert items[0]["source"] == {"dicomid": "/tmp/video.dcm", "frame": 17}


def test_try_resume_from_old_and_new_json_formats(tmp_path: Path) -> None:
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    dicom_path = str((tmp_path / "patient_1" / "exam_1" / "case1.dcm").resolve())

    old_path.write_text(
        '{"predictions":[{"patient_id":"patient_1","exams":[{"exam_id":"exam_1","dicoms":[{"file_path":"'
        + dicom_path
        + '","measurements":[{"order":1,"text":"LVIDd 5.2 cm"}]}]}]}]}',
        encoding="utf-8",
    )
    new_path.write_text(
        '{"patient_1":{"exam_1":{"dicoms":[{"file_path":"'
        + dicom_path
        + '","measurements":["LVIDd 5.2 cm"]}]}}}',
        encoding="utf-8",
    )

    old_items, old_processed = headless_batch_label._try_resume_from_json(old_path)
    new_items, new_processed = headless_batch_label._try_resume_from_json(new_path)

    assert old_processed == {dicom_path}
    assert new_processed == {dicom_path}
    assert old_items[0]["line_predictions"] == [{"order": 1, "text": "LVIDd 5.2 cm"}]
    assert new_items[0]["line_predictions"] == [{"order": 1, "text": "LVIDd 5.2 cm"}]


def test_batch_status_code_classifies_all_requested_states() -> None:
    assert headless_batch_label._batch_status_code(
        {"line_predictions": [], "measurements": [], "error": None}
    ) == 0
    assert headless_batch_label._batch_status_code(
        {
            "line_predictions": [{"text": "LVIDd ??? cm"}],
            "measurements": [],
            "error": {"type": "PipelineError", "message": "ocr failed"},
        }
    ) == 1
    assert headless_batch_label._batch_status_code(
        {
            "line_predictions": [{"text": "LVIDd 5.2 cm", "manual_verify_required": True}],
            "measurements": [{"name": "LVIDd", "value": "5.2"}],
            "error": None,
        }
    ) == 2
    assert headless_batch_label._batch_status_code(
        {
            "line_predictions": [{"text": "LVIDd 5.2 cm"}],
            "measurements": [{"name": "LVIDd", "value": "5.2"}],
            "error": None,
        }
    ) == 3


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
