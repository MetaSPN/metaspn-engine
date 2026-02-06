"""Tests for M1 profile -> score -> route reference orchestration."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.m1_routing import (
    M1RoutingState,
    build_m1_routing_pipeline,
    make_m1_signal,
)


def test_m1_reference_flow_has_stable_trace_sequence() -> None:
    engine = Engine(
        pipeline=build_m1_routing_pipeline(),
        initial_state=M1RoutingState(),
    )
    signal = make_m1_signal(
        signal_id="sig_m1_1",
        timestamp=datetime(2026, 2, 6, 14, 0, 0),
        source="ops.m1.worker",
        profile_id="p_1",
        profile_tier="core",
        quality_score=0.8,
        intent_score=0.7,
        channel="social",
    )

    emissions = engine.process(signal)

    assert [item.emission_id for item in emissions] == [
        "sig_m1_1:profile",
        "sig_m1_1:score",
        "sig_m1_1:route",
    ]
    assert [item.emission_type for item in emissions] == [
        "m1.profile.enriched",
        "m1.scores.computed",
        "m1.route.selected",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m1_1",
        "sig_m1_1",
        "sig_m1_1",
    ]
    assert emissions[1].payload["route_hint"] == "priority_review"
    assert emissions[2].payload["route"] == "priority_review"

    state = engine.get_state()
    assert state.profiled_count == 1
    assert state.scored_count == 1
    assert state.routed_count == 1
    assert state.last_route == "priority_review"


def test_m1_batch_flow_order_is_deterministic() -> None:
    engine = Engine(
        pipeline=build_m1_routing_pipeline(),
        initial_state=M1RoutingState(),
    )

    s1 = make_m1_signal(
        signal_id="sig_m1_2",
        timestamp=datetime(2026, 2, 6, 14, 1, 0),
        source="ops.m1.worker",
        profile_id="p_2",
        profile_tier="core",
        quality_score=0.3,
        intent_score=0.5,
        channel="social",
    )
    s2 = make_m1_signal(
        signal_id="sig_m1_3",
        timestamp=datetime(2026, 2, 6, 14, 2, 0),
        source="ops.m1.worker",
        profile_id="p_3",
        profile_tier="edge",
        quality_score=0.9,
        intent_score=0.9,
        channel="social",
    )

    emissions = engine.process_batch([s1, s2])

    assert [item.emission_id for item in emissions] == [
        "sig_m1_2:profile",
        "sig_m1_2:score",
        "sig_m1_2:route",
        "sig_m1_3:profile",
        "sig_m1_3:score",
        "sig_m1_3:route",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m1_2",
        "sig_m1_2",
        "sig_m1_2",
        "sig_m1_3",
        "sig_m1_3",
        "sig_m1_3",
    ]
    assert emissions[2].payload["route"] == "standard_queue"
    assert emissions[5].payload["route"] == "priority_review"
