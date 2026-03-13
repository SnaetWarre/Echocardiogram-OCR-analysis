from __future__ import annotations

from pathlib import Path

from app.tools.eval_line_transcription import _match_count


def test_match_count_scores_exact_and_structured_fields() -> None:
    result = _match_count(
        ["1 IVSd 0.9 cm", "2 LVIDd 5.4 cm"],
        ["1 IVSd 0.9 cm", "2 LVIDd 5.5 cm"],
    )

    assert result["exact"] == 1
    assert result["label"] == 2
    assert result["value"] == 1
