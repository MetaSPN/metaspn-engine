"""Tests for M3 attempt/outcome/failure/calibration reference flow."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.m3_learning import (
    M3LearningState,
    build_m3_learning_pipeline,
    make_m3_signal,
)


def test_m3_stage_order_and_traceability_are_deterministic() -> None:
    engine = Engine(
        pipeline=build_m3_learning_pipeline(),
        initial_state=M3LearningState(),
    )
    signal = make_m3_signal(
        signal_id="sig_m3_1",
        timestamp=datetime(2026, 2, 6, 16, 0, 0),
        source="ops.m3.worker",
        learner_id="l_1",
        skill_id="skill_a",
        attempt_id="attempt_1",
        expected_score=0.8,
        observed_score=0.62,
    )

    emissions = engine.process(signal)

    assert [item.emission_id for item in emissions] == [
        "sig_m3_1:attempt",
        "sig_m3_1:outcome",
        "sig_m3_1:failure",
        "sig_m3_1:calibration",
    ]
    assert [item.emission_type for item in emissions] == [
        "m3.attempt.snapshot",
        "m3.outcome.evaluated",
        "m3.failure.classified",
        "m3.calibration.proposed",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m3_1",
        "sig_m3_1",
        "sig_m3_1",
        "sig_m3_1",
    ]
    assert emissions[1].payload["gap"] == 0.18
    assert emissions[2].payload["failure_class"] == "major_gap"
    assert emissions[3].payload["proposal"] == "rebuild_foundation"


def test_m3_batch_order_and_caused_by_chain_are_stable() -> None:
    engine = Engine(
        pipeline=build_m3_learning_pipeline(),
        initial_state=M3LearningState(),
    )

    s1 = make_m3_signal(
        signal_id="sig_m3_2",
        timestamp=datetime(2026, 2, 6, 16, 1, 0),
        source="ops.m3.worker",
        learner_id="l_2",
        skill_id="skill_b",
        attempt_id="attempt_2",
        expected_score=0.7,
        observed_score=0.69,
    )
    s2 = make_m3_signal(
        signal_id="sig_m3_3",
        timestamp=datetime(2026, 2, 6, 16, 2, 0),
        source="ops.m3.worker",
        learner_id="l_3",
        skill_id="skill_c",
        attempt_id="attempt_3",
        expected_score=0.65,
        observed_score=0.66,
    )

    emissions = engine.process_batch([s1, s2])

    assert [item.emission_id for item in emissions] == [
        "sig_m3_2:attempt",
        "sig_m3_2:outcome",
        "sig_m3_2:failure",
        "sig_m3_2:calibration",
        "sig_m3_3:attempt",
        "sig_m3_3:outcome",
        "sig_m3_3:failure",
        "sig_m3_3:calibration",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m3_2",
        "sig_m3_2",
        "sig_m3_2",
        "sig_m3_2",
        "sig_m3_3",
        "sig_m3_3",
        "sig_m3_3",
        "sig_m3_3",
    ]
    assert emissions[3].payload["proposal"] == "increase_support"
    assert emissions[7].payload["proposal"] == "maintain"
