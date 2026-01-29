"""Minimal smoke tests for the MetaSPN Engine."""

from dataclasses import dataclass
from datetime import datetime


from metaspn_engine import Signal, Pipeline, Engine
from metaspn_engine.transforms import accumulate, update_state, emit_if


@dataclass(frozen=True)
class ScoreEvent:
    """Simple signal payload for tests."""
    user_id: str
    score: float


@dataclass
class GameState:
    """Simple state for tests."""
    total_signals: int = 0
    running_total: float = 0.0
    high_score: float = 0.0


def test_engine_processes_signal_and_updates_state():
    """Engine processes a signal through pipeline and updates state."""
    pipeline = Pipeline([
        accumulate("total_signals", lambda acc, _: (acc or 0) + 1),
        accumulate("running_total", lambda acc, p: (acc or 0.0) + p.score),
        update_state(
            lambda payload, state: GameState(
                total_signals=state.total_signals,
                running_total=state.running_total,
                high_score=max(state.high_score, payload.score),
            )
            if payload.score > state.high_score
            else state
        ),
    ], name="test_pipeline")

    engine = Engine(pipeline=pipeline, initial_state=GameState())

    signal = Signal(
        payload=ScoreEvent(user_id="user_123", score=95.5),
        timestamp=datetime.now(),
        source="test",
    )

    emissions = engine.process(signal)

    state = engine.get_state()
    assert state.total_signals == 1
    assert state.running_total == 95.5
    assert state.high_score == 95.5
    assert isinstance(emissions, list)


def test_engine_emit_if_produces_emission():
    """Pipeline with emit_if produces emission when condition is true."""
    pipeline = Pipeline([
        accumulate("total_signals", lambda acc, _: (acc or 0) + 1),
        accumulate("high_score", lambda acc, p: max(acc or 0.0, p.score)),
        emit_if(
            condition=lambda payload, state: payload.score >= (getattr(state, "high_score", 0) or 0),
            emission_type="new_high_score",
            payload_extractor=lambda payload, state: {
                "user_id": payload.user_id,
                "score": payload.score,
            },
        ),
    ], name="emit_test")

    @dataclass
    class SimpleState:
        total_signals: int = 0
        high_score: float = 0.0

    engine = Engine(pipeline=pipeline, initial_state=SimpleState())

    signal = Signal(
        payload=ScoreEvent(user_id="user_1", score=80.0),
        timestamp=datetime.now(),
        source="test",
    )

    emissions = engine.process(signal)

    assert len(emissions) == 1
    assert emissions[0].emission_type == "new_high_score"
    assert emissions[0].payload["score"] == 80.0
    assert emissions[0].caused_by == signal.signal_id
