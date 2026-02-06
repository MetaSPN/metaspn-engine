"""Tests for the M0 ingestion reference orchestration path."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.m0_ingestion import (
    M0IngestionState,
    build_m0_ingestion_pipeline,
    make_m0_signal,
)


def test_m0_reference_flow_is_traceable_and_deterministic() -> None:
    engine = Engine(
        pipeline=build_m0_ingestion_pipeline(),
        initial_state=M0IngestionState(),
    )
    signal = make_m0_signal(
        signal_id="sig_m0_1",
        timestamp=datetime(2026, 2, 6, 13, 0, 0),
        source="ops.m0.worker",
        platform="x",
        external_id="post_1",
        actor_ref="user_1",
        content_hash="hash_1",
    )

    emissions = engine.process(signal)

    assert [item.emission_id for item in emissions] == [
        "sig_m0_1:ingest",
        "sig_m0_1:resolve",
        "sig_m0_1:emit",
    ]
    assert [item.emission_type for item in emissions] == [
        "m0.ingest.accepted",
        "m0.resolve.completed",
        "m0.event.ready",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m0_1",
        "sig_m0_1",
        "sig_m0_1",
    ]

    state = engine.get_state()
    assert state.ingested_count == 1
    assert state.resolved_count == 1
    assert state.last_entity_ref == "x:user_1"


def test_m0_batch_ordering_is_stable_for_multiple_signals() -> None:
    engine = Engine(
        pipeline=build_m0_ingestion_pipeline(),
        initial_state=M0IngestionState(),
    )

    s1 = make_m0_signal(
        signal_id="sig_m0_2",
        timestamp=datetime(2026, 2, 6, 13, 1, 0),
        source="ops.m0.worker",
        platform="x",
        external_id="post_2",
        actor_ref="user_2",
        content_hash="hash_2",
    )
    s2 = make_m0_signal(
        signal_id="sig_m0_3",
        timestamp=datetime(2026, 2, 6, 13, 2, 0),
        source="ops.m0.worker",
        platform="x",
        external_id="post_3",
        actor_ref="user_3",
        content_hash="hash_3",
    )

    emissions = engine.process_batch([s1, s2])

    assert [item.emission_id for item in emissions] == [
        "sig_m0_2:ingest",
        "sig_m0_2:resolve",
        "sig_m0_2:emit",
        "sig_m0_3:ingest",
        "sig_m0_3:resolve",
        "sig_m0_3:emit",
    ]
    assert [item.caused_by for item in emissions] == [
        "sig_m0_2",
        "sig_m0_2",
        "sig_m0_2",
        "sig_m0_3",
        "sig_m0_3",
        "sig_m0_3",
    ]
