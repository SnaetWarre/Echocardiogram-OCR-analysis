from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from app.models.types import AiMeasurement, AiResult, PipelineResult
import app.tools.batch.headless_batch_label as mod


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, request):
        path = Path(request.dicom_path)
        self.calls.append(str(path))
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


root = Path(tempfile.mkdtemp())
(root / "one.dcm").write_bytes(b"x")
(root / "two.dcm").write_bytes(b"x")
checkpoint = root / "resume.checkpoint.json"
checkpoint.write_text(
    json.dumps(
        {
            "version": 1,
            "items": [
                {
                    "dicom_path": str((root / "one.dcm").resolve()),
                    "status": "ok",
                    "measurements": [],
                    "metadata": {},
                    "error": None,
                }
            ],
        }
    ),
    encoding="utf-8",
)
fake = FakePipeline()
mod._build_pipeline = lambda _args: fake
args = Namespace(
    input_path=root,
    pattern="*.dcm",
    recursive=True,
    max_files=0,
    output=root / "results",
    output_format="json",
    engine="glm-ocr",
    fallback_engine="surya",
    strict_engine_selection=False,
    max_frames=0,
    continue_on_error=True,
    resume=True,
    checkpoint_path=checkpoint,
    checkpoint_interval=1,
    preflight=False,
    run_id="",
    run_tag="",
    run_note="",
)
print("exit", mod.run_batch(args))
print("calls", fake.calls)
