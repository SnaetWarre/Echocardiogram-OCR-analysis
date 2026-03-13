from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from app.tools.eval_line_transcription import _match_count, evaluate_line_transcription


def test_match_count_scores_exact_and_structured_fields() -> None:
    result = _match_count(
        ["1 IVSd 0.9 cm", "2 LVIDd 5.4 cm"],
        ["1 IVSd 0.9 cm", "2 LVIDd 5.5 cm"],
    )

    assert result["exact"] == 1
    assert result["label"] == 2
    assert result["value"] == 1


def test_eval_counts_panel_lines_even_when_measurements_do_not_decode(monkeypatch, tmp_path: Path) -> None:
    class _FakeSeries:
        frame_count = 1

        def get_frame(self, index: int) -> object:
            _ = index
            return object()

    class _FakePipeline:
        def __init__(self, *args, **kwargs) -> None:
            _ = args, kwargs
            self.box_detector = SimpleNamespace(detect=lambda _frame: SimpleNamespace(present=True, bbox=(0, 0, 10, 10)))

        def ensure_components(self) -> None:
            return None

        def analyze_frame_with_debug(self, frame: object):
            _ = frame
            panel = SimpleNamespace(
                lines=(SimpleNamespace(text="nonsense line", uncertain=False),),
                uncertain_line_count=0,
                fallback_invocations=0,
                engine_disagreement_count=0,
            )
            segmentation = SimpleNamespace(lines=(SimpleNamespace(),))
            detection = SimpleNamespace(present=True, bbox=(0, 0, 10, 10))
            return detection, segmentation, None, panel, [], None

    label = SimpleNamespace(
        path=tmp_path / "example.dcm",
        file_name="example.dcm",
        split="validation",
        measurements=[SimpleNamespace(text="1 Expected 1.0 cm")],
    )
    label.path.write_bytes(b"dicom")

    monkeypatch.setattr("app.tools.eval_line_transcription.EchoOcrPipeline", _FakePipeline)
    monkeypatch.setattr("app.io.dicom_loader.load_dicom_series", lambda _path, load_pixels=True: _FakeSeries())

    totals = evaluate_line_transcription(cast(list, [label]), engine_name="surya", fallback_engine_name="")

    assert totals.ocr_predictions == 1
    assert totals.file_reports[0]["predicted_lines"] == ["nonsense line"]
