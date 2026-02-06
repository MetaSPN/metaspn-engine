"""Tests for M2 recommendation ranking and draft reference flow."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.m2_recommendations import (
    M2RecommendationState,
    RecommendationCandidate,
    build_m2_recommendation_pipeline,
    make_m2_signal,
)


def test_m2_ranking_is_deterministic_for_equal_and_near_equal_scores() -> None:
    engine = Engine(
        pipeline=build_m2_recommendation_pipeline(),
        initial_state=M2RecommendationState(),
    )
    signal = make_m2_signal(
        signal_id="sig_m2_1",
        timestamp=datetime(2026, 2, 6, 15, 0, 0),
        source="ops.m2.worker",
        audience_id="aud_1",
        prompt="Draft recommendation",
        candidates=(
            RecommendationCandidate(candidate_id="c", title="Gamma", score=0.8000, context_boost=0.0),
            RecommendationCandidate(candidate_id="b", title="Beta", score=0.7999, context_boost=0.0001),
            RecommendationCandidate(candidate_id="a", title="Alpha", score=0.8, context_boost=0.0),
        ),
    )

    emissions = engine.process(signal)

    assert [item.emission_id for item in emissions] == [
        "sig_m2_1:recommendation",
        "sig_m2_1:draft",
    ]
    ranked_payload = emissions[0].payload
    assert ranked_payload["ranked_ids"] == ["a", "b", "c"]
    assert ranked_payload["top_candidate_id"] == "a"
    assert emissions[1].payload["recommended_candidate_id"] == "a"


def test_m2_emissions_preserve_caused_by_and_batch_order() -> None:
    engine = Engine(
        pipeline=build_m2_recommendation_pipeline(),
        initial_state=M2RecommendationState(),
    )

    s1 = make_m2_signal(
        signal_id="sig_m2_2",
        timestamp=datetime(2026, 2, 6, 15, 1, 0),
        source="ops.m2.worker",
        audience_id="aud_2",
        prompt="Draft recommendation",
        candidates=(
            RecommendationCandidate(candidate_id="x2", title="Item X2", score=0.4, context_boost=0.0),
            RecommendationCandidate(candidate_id="x1", title="Item X1", score=0.6, context_boost=0.1),
        ),
    )
    s2 = make_m2_signal(
        signal_id="sig_m2_3",
        timestamp=datetime(2026, 2, 6, 15, 2, 0),
        source="ops.m2.worker",
        audience_id="aud_3",
        prompt="Draft recommendation",
        candidates=(
            RecommendationCandidate(candidate_id="y1", title="Item Y1", score=0.7, context_boost=0.0),
            RecommendationCandidate(candidate_id="y2", title="Item Y2", score=0.7, context_boost=0.0),
        ),
    )

    emissions = engine.process_batch([s1, s2])

    assert [item.emission_id for item in emissions] == [
        "sig_m2_2:recommendation",
        "sig_m2_2:draft",
        "sig_m2_3:recommendation",
        "sig_m2_3:draft",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m2_2",
        "sig_m2_2",
        "sig_m2_3",
        "sig_m2_3",
    ]
    assert emissions[1].payload["recommended_candidate_id"] == "x1"
    assert emissions[3].payload["recommended_candidate_id"] == "y1"
