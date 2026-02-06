"""Contract-safety tests for IDs, serialization boundaries, and traceability."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from metaspn_engine import Engine, Pipeline, Signal
from metaspn_engine.transforms import emit, emit_if


@dataclass(frozen=True)
class ScoreEvent:
    user_id: str
    score: float


def test_signal_round_trip_preserves_identity_and_metadata() -> None:
    timestamp = datetime(2026, 2, 6, 10, 0, 0)
    signal = Signal(
        payload={"score": 88.2},
        timestamp=timestamp,
        source="ingestor.contract",
        signal_id="sig_123",
        metadata={"trace_id": "tr_abc"},
    )

    serialized = signal.to_dict()
    restored = Signal.from_dict(serialized, payload_factory=lambda payload: payload)

    assert restored.signal_id == "sig_123"
    assert restored.timestamp == timestamp
    assert restored.metadata["trace_id"] == "tr_abc"
    assert restored.payload == {"score": 88.2}


def test_emit_if_supports_deterministic_id_and_timestamp() -> None:
    signal_timestamp = datetime(2026, 2, 6, 11, 0, 0)
    signal = Signal(
        payload=ScoreEvent(user_id="u1", score=90.0),
        timestamp=signal_timestamp,
        source="ingestor.contract",
        signal_id="sig_456",
    )

    pipeline = Pipeline(
        [
            emit_if(
                condition=lambda payload, state: payload.score > 80.0,
                emission_type="score_high",
                payload_extractor=lambda payload, state: {"score": payload.score},
                emission_id_factory=lambda sig, state: f"{sig.signal_id}:score_high",
                timestamp_factory=lambda sig, state: sig.timestamp,
            )
        ],
        name="deterministic_emit_if",
    )
    engine = Engine(pipeline=pipeline, initial_state={})

    emissions = engine.process(signal)

    assert len(emissions) == 1
    assert emissions[0].emission_id == "sig_456:score_high"
    assert emissions[0].timestamp == signal_timestamp
    assert emissions[0].caused_by == "sig_456"


def test_batch_processing_preserves_traceability_and_emission_ordering() -> None:
    pipeline = Pipeline(
        [
            emit(
                emission_type="first",
                payload_extractor=lambda payload, state: {"user": payload.user_id},
                emission_id_factory=lambda sig, state: f"{sig.signal_id}:first",
                timestamp_factory=lambda sig, state: sig.timestamp,
            ),
            emit(
                emission_type="second",
                payload_extractor=lambda payload, state: {"score": payload.score},
                emission_id_factory=lambda sig, state: f"{sig.signal_id}:second",
                timestamp_factory=lambda sig, state: sig.timestamp + timedelta(seconds=1),
            ),
        ],
        name="ordering_contract",
    )
    engine = Engine(pipeline=pipeline, initial_state={})

    s1 = Signal(
        payload=ScoreEvent(user_id="u1", score=70.0),
        timestamp=datetime(2026, 2, 6, 12, 0, 0),
        source="ingestor.contract",
        signal_id="sig_1",
    )
    s2 = Signal(
        payload=ScoreEvent(user_id="u2", score=75.0),
        timestamp=datetime(2026, 2, 6, 12, 0, 5),
        source="ingestor.contract",
        signal_id="sig_2",
    )

    emissions = engine.process_batch([s1, s2])

    assert [e.emission_id for e in emissions] == [
        "sig_1:first",
        "sig_1:second",
        "sig_2:first",
        "sig_2:second",
    ]
    assert [e.caused_by for e in emissions] == ["sig_1", "sig_1", "sig_2", "sig_2"]
    assert [e.emission_type for e in emissions] == ["first", "second", "first", "second"]
    assert [e.timestamp for e in emissions] == [
        datetime(2026, 2, 6, 12, 0, 0),
        datetime(2026, 2, 6, 12, 0, 1),
        datetime(2026, 2, 6, 12, 0, 5),
        datetime(2026, 2, 6, 12, 0, 6),
    ]
