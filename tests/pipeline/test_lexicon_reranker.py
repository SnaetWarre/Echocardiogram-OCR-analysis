from __future__ import annotations

from app.pipeline.lexicon_builder import LexiconArtifact, NumericStats
from app.pipeline.lexicon_reranker import LexiconReranker
from app.pipeline.line_transcriber import LineOcrCandidate, LinePrediction, PanelTranscription


def _artifact() -> LexiconArtifact:
    return LexiconArtifact(
        artifact_version=1,
        created_at="now",
        labels_path="labels/exact_lines.json",
        dataset_version=1,
        dataset_task="exact_roi_measurement_transcription",
        total_files=1,
        total_lines=2,
        exact_line_frequencies={"1 ivsd 0.9 cm": 0, "1 IVSd 0.9 cm": 2},
        label_frequencies={"ivsd": 2},
        label_family_lines={"ivsd": ["1 IVSd 0.9 cm"]},
        label_unit_frequencies={"ivsd": {"cm": 2}},
        label_order_frequencies={"ivsd": {"1": 2}},
        label_value_stats={"ivsd": NumericStats(count=2, min=0.9, max=1.0, mean=0.95)},
        token_frequencies={"ivsd": 2},
        unit_frequencies={"cm": 2},
        prefix_frequencies={"1": 2},
        line_pattern_frequencies={"<PREFIX> ivsd <VALUE> <UNIT:cm>": 2},
    )


def test_lexicon_reranker_prefers_known_label_family() -> None:
    reranker = LexiconReranker(_artifact())
    ranked = reranker.rank_candidates(
        [
            LineOcrCandidate(text="1 IVSd 0.9 cm", confidence=0.7, engine_name="a", view_name="default", source="primary"),
            LineOcrCandidate(text="1 IVSd 0.9 em", confidence=0.75, engine_name="b", view_name="default", source="fallback"),
        ],
        line_order=0,
    )

    assert ranked[0].candidate.text == "1 IVSd 0.9 cm"


def test_lexicon_reranker_updates_panel_with_best_candidate() -> None:
    reranker = LexiconReranker(_artifact())
    panel = PanelTranscription(
        lines=(
            LinePrediction(
                order=0,
                bbox=(0, 0, 10, 10),
                text="1 IVSd 0.9 em",
                confidence=0.75,
                engine_name="b",
                source="fallback",
                uncertain=True,
                candidates=(
                    LineOcrCandidate(text="1 IVSd 0.9 em", confidence=0.75, engine_name="b", view_name="default", source="fallback"),
                    LineOcrCandidate(text="1 IVSd 0.9 cm", confidence=0.7, engine_name="a", view_name="default", source="primary"),
                ),
            ),
        ),
        combined_text="1 IVSd 0.9 em",
        uncertain_line_count=1,
    )

    reranked = reranker.rerank_panel(panel)

    assert reranked.lines[0].text == "1 IVSd 0.9 cm"


def test_lexicon_reranker_prefers_label_before_value_candidate_for_dense_rows() -> None:
    reranker = LexiconReranker(
        LexiconArtifact(
            artifact_version=1,
            created_at="now",
            labels_path="labels/exact_lines.json",
            dataset_version=1,
            dataset_task="exact_roi_measurement_transcription",
            total_files=1,
            total_lines=1,
            exact_line_frequencies={"LVEF MOD A2C 62.09 %": 2},
            label_frequencies={"lvef mod a2c": 2},
            label_family_lines={"lvef mod a2c": ["LVEF MOD A2C 62.09 %"]},
            label_unit_frequencies={"lvef mod a2c": {"%": 2}},
            label_order_frequencies={"lvef mod a2c": {"4": 2}},
            label_value_stats={},
            token_frequencies={"lvef": 2},
            unit_frequencies={"%": 2},
            prefix_frequencies={},
            line_pattern_frequencies={"lvef mod a2c <VALUE> <UNIT:%>": 2},
        )
    )

    ranked = reranker.rank_candidates(
        [
            LineOcrCandidate(text="62.09 % LVEF MOD A2C", confidence=0.99, engine_name="surya", view_name="default", source="primary"),
            LineOcrCandidate(text="LVEF MOD A2C 62.09 %", confidence=0.95, engine_name="surya", view_name="clahe", source="primary_multiview"),
        ],
        line_order=3,
    )

    assert ranked[0].candidate.text == "LVEF MOD A2C 62.09 %"
