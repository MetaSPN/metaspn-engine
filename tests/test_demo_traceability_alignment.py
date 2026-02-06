"""Demo alignment tests for deterministic stage ordering and trace linkage."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.demo_support import demo_stage_specs, expected_emission_ids
from metaspn_engine.m2_recommendations import (
    M2RecommendationState,
    RecommendationCandidate,
    build_m2_recommendation_pipeline,
    make_m2_signal,
)
from metaspn_engine.m3_learning import (
    M3LearningState,
    build_m3_learning_pipeline,
    make_m3_signal,
)


def test_demo_stage_specs_have_expected_reference_suffixes() -> None:
    specs = demo_stage_specs()
    assert tuple(specs["m2_shortlist"].emission_suffixes) == ("recommendation", "draft")
    assert tuple(specs["m3_learning"].emission_suffixes) == ("attempt", "outcome", "failure", "calibration")
    assert expected_emission_ids("sig_demo", "m2_shortlist") == [
        "sig_demo:recommendation",
        "sig_demo:draft",
    ]


def test_demo_shortlist_and_learning_traces_are_deterministic() -> None:
    m2_engine = Engine(
        pipeline=build_m2_recommendation_pipeline(),
        initial_state=M2RecommendationState(),
    )
    m3_engine = Engine(
        pipeline=build_m3_learning_pipeline(),
        initial_state=M3LearningState(),
    )

    shortlist_signal = make_m2_signal(
        signal_id="sig_demo_m2",
        timestamp=datetime(2026, 2, 6, 17, 0, 0),
        source="demo.orchestrator",
        audience_id="aud_demo",
        prompt="Build shortlist",
        candidates=(
            RecommendationCandidate(candidate_id="c2", title="Choice 2", score=0.7, context_boost=0.1),
            RecommendationCandidate(candidate_id="c1", title="Choice 1", score=0.8, context_boost=0.0),
        ),
    )
    learning_signal = make_m3_signal(
        signal_id="sig_demo_m3",
        timestamp=datetime(2026, 2, 6, 17, 1, 0),
        source="demo.orchestrator",
        learner_id="learner_demo",
        skill_id="skill_demo",
        attempt_id="attempt_demo",
        expected_score=0.75,
        observed_score=0.6,
    )

    shortlist_emissions = m2_engine.process(shortlist_signal)
    learning_emissions = m3_engine.process(learning_signal)

    assert [item.emission_id for item in shortlist_emissions] == expected_emission_ids("sig_demo_m2", "m2_shortlist")
    assert [item.caused_by for item in shortlist_emissions] == ["sig_demo_m2", "sig_demo_m2"]
    assert shortlist_emissions[0].payload["top_candidate_id"] == "c1"

    assert [item.emission_id for item in learning_emissions] == expected_emission_ids("sig_demo_m3", "m3_learning")
    assert [item.caused_by for item in learning_emissions] == [
        "sig_demo_m3",
        "sig_demo_m3",
        "sig_demo_m3",
        "sig_demo_m3",
    ]
    assert learning_emissions[3].payload["proposal"] == "rebuild_foundation"
