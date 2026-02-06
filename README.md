# MetaSPN Engine

**Minimal signal processing engine for observable games.**

Zero game semantics. Pure signal flow. Maximum composability.

## Philosophy

The MetaSPN Engine is a **dumb pipe**. It knows nothing about podcasts, tweets, G1-G6 games, or any domain-specific concepts. It only knows:

- **Signals** flow in (typed, timestamped, immutable)
- **Pipelines** process them (pure functions, composable)
- **State** accumulates (typed, versioned)
- **Emissions** flow out (typed, traceable)

Everything else is built on top through game wrappers.

## Installation

```bash
pip install metaspn-engine
```

## Quick Start

```python
from dataclasses import dataclass
from datetime import datetime
from metaspn_engine import Signal, Emission, State, Pipeline, Engine
from metaspn_engine.transforms import emit_if, accumulate, update_state

# 1. Define your signal payload type
@dataclass(frozen=True)
class ScoreEvent:
    user_id: str
    score: float

# 2. Define your state type
@dataclass
class GameState:
    total_signals: int = 0
    running_total: float = 0.0
    high_score: float = 0.0

# 3. Build your pipeline
pipeline = Pipeline([
    # Count signals
    accumulate("total_signals", lambda acc, _: (acc or 0) + 1),
    
    # Track running total
    accumulate("running_total", lambda acc, payload: (acc or 0) + payload.score),
    
    # Update high score
    update_state(lambda payload, state: 
        GameState(
            total_signals=state.total_signals,
            running_total=state.running_total,
            high_score=max(state.high_score, payload.score)
        ) if payload.score > state.high_score else state
    ),
    
    # Emit on high score
    emit_if(
        condition=lambda payload, state: payload.score > state.high_score,
        emission_type="new_high_score",
        payload_extractor=lambda payload, state: {
            "user_id": payload.user_id,
            "score": payload.score,
            "previous_high": state.high_score,
        }
    ),
])

# 4. Create engine
engine = Engine(
    pipeline=pipeline,
    initial_state=GameState(),
)

# 5. Process signals
signal = Signal(
    payload=ScoreEvent(user_id="user_123", score=95.5),
    timestamp=datetime.now(),
    source="game_server",
)

emissions = engine.process(signal)

# 6. Check results
print(f"State: {engine.get_state()}")
print(f"Emissions: {emissions}")
```

## Core Concepts

### Signals

Immutable input events with typed payloads:

```python
@dataclass(frozen=True)
class PodcastListen:
    episode_id: str
    duration_seconds: int
    completed: bool

signal = Signal(
    payload=PodcastListen("ep_123", 3600, True),
    timestamp=datetime.now(),
    source="overcast",
)
```

### Pipelines

Sequences of pure steps that process signals:

```python
pipeline = Pipeline([
    step_one,
    step_two,
    step_three,
], name="my_pipeline")

# Pipelines are composable
combined = pipeline_a + pipeline_b

# Pipelines support branching
branched = pipeline.branch(
    predicate=lambda s: s.payload.type == "podcast",
    if_true=podcast_pipeline,
    if_false=other_pipeline,
)
```

### State

Mutable accumulated context:

```python
@dataclass
class MyState:
    count: int = 0
    items: list = field(default_factory=list)

state = State(value=MyState())
state.enable_history()  # Track state transitions

# State updates happen through pipeline steps
# using update functions
```

### Emissions

Immutable output events:

```python
emission = Emission(
    payload={"score": 0.85},
    caused_by=signal.signal_id,  # Traceability
    emission_type="score_computed",
)
```

## Transforms

Built-in step functions for common operations:

```python
from metaspn_engine.transforms import (
    # Mapping
    map_to_emission,
    
    # State management
    accumulate,
    set_state,
    update_state,
    
    # Windowing
    window,
    time_window,
    
    # Emissions
    emit,
    emit_if,
    emit_on_change,
    
    # Control flow
    branch,
    merge,
    sequence,
    
    # Utilities
    log,
    tap,
)
```

## Building Game Wrappers

The engine is meant to be wrapped by game-specific packages:

```python
# metaspn_podcast/game.py
from metaspn_engine import Signal, Pipeline, Engine
from metaspn_engine.protocols import GameProtocol

class PodcastGame:
    """Podcast listening game built on MetaSPN Engine."""
    
    name = "podcast"
    version = "1.0.0"
    
    def create_signal(self, data: dict) -> Signal[PodcastListen]:
        return Signal(
            payload=PodcastListen(
                episode_id=data["episode_id"],
                duration_seconds=data["duration"],
                completed=data.get("completed", False),
            ),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "unknown"),
        )
    
    def initial_state(self) -> PodcastState:
        return PodcastState()
    
    def pipeline(self) -> Pipeline:
        return Pipeline([
            track_listening,
            compute_influence_vector,
            update_trajectory,
            emit_if_significant,
        ])

# Usage
game = PodcastGame()
engine = Engine(
    pipeline=game.pipeline(),
    initial_state=game.initial_state(),
)

for event in listening_events:
    signal = game.create_signal(event)
    emissions = engine.process(signal)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Game Wrappers                           │
│  (PodcastGame, TwitterGame, CreatorScoring, etc.)          │
│                                                             │
│  - Define signal types                                      │
│  - Define state shape                                       │
│  - Build domain-specific pipelines                          │
│  - Handle game-specific logic                               │
└─────────────────────────────────────────────────────────────┘
                            │
                    implements GameProtocol
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  metaspn-engine (core)                      │
│                                                             │
│   Signal[T] ──▶ Pipeline[Steps] ──▶ Emission[U]            │
│                      │                                      │
│               reads/writes                                  │
│                      │                                      │
│                 State[S]                                    │
│                                                             │
│  - Type-safe signal flow                                    │
│  - Pure function pipelines                                  │
│  - Versioned state management                               │
│  - Traceable emissions                                      │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Zero Dependencies** - The core engine has no external dependencies
2. **Pure Functions** - All transforms are pure (state updates are explicit)
3. **Type Safety** - Full generic type support for signals, state, emissions
4. **Composability** - Pipelines compose, games compose, everything composes
5. **Traceability** - Every emission traces back to its causing signal
6. **Testability** - Given input + state, output is deterministic

## Integration Guardrails (schemas/store/ops)

When integrating `metaspn-engine` with `metaspn-schemas`, `metaspn-store`, and `metaspn-ops`, use these contract boundaries:

1. **Stable IDs are caller-owned**
   - `Signal.signal_id` should be generated before engine processing and reused on retries.
   - If downstream storage is idempotent by `emission_id`, emit deterministic IDs (do not rely on random defaults during retry flows).
   - Use `emit`, `emit_if`, or `map_to_emission` with `emission_id_factory` when deterministic IDs are required.

2. **Serialization boundary is dictionary payloads**
   - `Signal.to_dict()` / `Signal.from_dict()` is the engine boundary for transport and persistence.
   - For envelope-level contracts (schema version, trace context, UTC normalization), map engine objects into `metaspn-schemas` `SignalEnvelope` and `EmissionEnvelope` at integration edges.

3. **Timestamp semantics**
   - `Signal.timestamp` is event time from the source.
   - `Emission.timestamp` defaults to processing time, but deterministic pipelines should set it explicitly with `timestamp_factory` in emission transforms.

4. **Deterministic ordering and trace linkage**
   - Engine emission order is deterministic for a given input order and step order.
   - Every emission must set `caused_by` to the originating `signal_id`; built-in emission transforms enforce this.

5. **Durable store/replay compatibility**
   - Keep engine steps pure and side-effect free; persist outputs through store adapters.
   - For replay-safe ops retries, treat `(signal_id, emission_id)` as immutable identifiers once written.

## M0 Orchestration Reference

`metaspn_engine.m0_ingestion` provides a minimal ingest -> resolve -> emit path for social ingestion.

- Reference objects:
  - `SocialIngestionEvent`
  - `M0IngestionState`
  - `build_m0_ingestion_pipeline()`
  - `make_m0_signal(...)`
- Emission contract:
  - `m0.ingest.accepted`
  - `m0.resolve.completed`
  - `m0.event.ready`
- Determinism:
  - Emission IDs are stable (`<signal_id>:ingest|resolve|emit`)
  - `caused_by` always equals source `signal_id`
  - Emission sequence follows step order for each signal

### Engine Directly vs Worker Orchestration

Use engine directly when:
- Running deterministic local processing in tests, replay tools, or single-process adapters.
- Input ordering and state lifecycle are controlled in-process.

Use worker-level orchestration (`metaspn-ops`) when:
- You need queue retries, dead-letter handling, and concurrency controls.
- You need durable signal/emission writes and replay windows through `metaspn-store`.
- You need envelope contract enforcement (`SignalEnvelope`, `EmissionEnvelope`) from `metaspn-schemas`.

## M1 Routing Reference

`metaspn_engine.m1_routing` provides a deterministic profile -> score -> route composition for M1 flows.

- Reference objects:
  - `M1ProfileSignal`
  - `M1RoutingState`
  - `build_m1_routing_pipeline()`
  - `make_m1_signal(...)`
- Emission contract:
  - `m1.profile.enriched`
  - `m1.scores.computed`
  - `m1.route.selected`
- Deterministic trace behavior:
  - Emission IDs are stable (`<signal_id>:profile|score|route`)
  - `caused_by` is preserved from the source signal
  - Stage outputs preserve fixed order for replay consistency

### M1 Composition vs Worker Orchestration

Use engine composition directly when:
- You want deterministic in-process stage chaining with explicit state transitions.
- You are building fixtures, integration tests, or local replay tooling.

Use worker orchestration (`metaspn-ops`) when:
- Stage boundaries map to separate workers/queues.
- You need durable handoff and idempotent persistence in `metaspn-store`.
- You need schema-envelope validation and versioned contracts from `metaspn-schemas`.

## M2 Recommendation Reference

`metaspn_engine.m2_recommendations` provides deterministic ranking -> draft composition for recommendation workers.

- Reference objects:
  - `RecommendationCandidate`
  - `M2RecommendationSignal`
  - `M2RecommendationState`
  - `build_m2_recommendation_pipeline()`
  - `make_m2_signal(...)`
- Emission contract:
  - `m2.recommendation.ranked`
  - `m2.draft.generated`
- Deterministic behavior:
  - Ranking key is stable and replay-friendly, including deterministic tie-breaks.
  - Emission IDs are stable (`<signal_id>:recommendation|draft`).
  - `caused_by` remains the original source `signal_id` for both stages.

### M2 Engine vs Worker Boundaries

Use engine-only composition when:
- Running deterministic recommendation simulations or fixture pipelines in-process.
- Verifying ranking and draft shaping logic before distributed rollout.

Use worker orchestration (`metaspn-ops`) when:
- Ranking and draft generation run in separate workers with queue handoff.
- You need persistent replay/idempotency guarantees from `metaspn-store`.
- You need schema contract/version checks via `metaspn-schemas` envelopes.

## M3 Learning Reference

`metaspn_engine.m3_learning` provides deterministic attempt -> outcome -> failure -> calibration composition.

- Reference objects:
  - `M3AttemptSignal`
  - `M3LearningState`
  - `build_m3_learning_pipeline()`
  - `make_m3_signal(...)`
- Emission contract:
  - `m3.attempt.snapshot`
  - `m3.outcome.evaluated`
  - `m3.failure.classified`
  - `m3.calibration.proposed`
- Deterministic trace behavior:
  - Stable emission IDs (`<signal_id>:attempt|outcome|failure|calibration`)
  - Stable stage order for replay
  - `caused_by` continuity from the source signal through calibration

### M3 Engine vs Worker Boundaries

Use engine composition directly when:
- Modeling learning logic in deterministic integration tests.
- Replaying attempt fixtures to verify stage outcomes.

Use worker orchestration (`metaspn-ops`) when:
- Attempt/outcome/failure/calibration stages run as separate workers.
- You need durable stage handoff, retries, and replay safety from `metaspn-store`.
- You need envelope validation/versioning from `metaspn-schemas`.

## Demo Traceability Mapping

Use `metaspn_engine.demo_support` as the source of truth for demo stage-to-pipeline mapping and expected deterministic emission IDs.

- Stage mapping:
  - `m0_ingest` -> `metaspn_engine.m0_ingestion` -> `ingest, resolve, emit`
  - `m1_route` -> `metaspn_engine.m1_routing` -> `profile, score, route`
  - `m2_shortlist` -> `metaspn_engine.m2_recommendations` -> `recommendation, draft`
  - `m3_learning` -> `metaspn_engine.m3_learning` -> `attempt, outcome, failure, calibration`
- Deterministic debug contract:
  - Emission IDs follow `<signal_id>:<stage_suffix>`
  - Emissions preserve stage order within each signal
  - All stage emissions preserve `caused_by=<signal_id>`
- Chaining guidance for demo orchestrator:
  - Chain stages by event envelope boundaries in `metaspn-ops` workers.
  - Use `metaspn-store` replay on signal IDs to trace full stage lineage.
  - Keep stage workers idempotent on stable IDs generated at the engine boundary.

## Why This Exists

MetaSPN measures transformation, not engagement. But transformation can happen in many contexts:

- Podcast listening → G3 (Models) learning
- Tweet threads → G2 (Idea Mining) extraction
- Creator output → G1 (Identity) development
- Network connections → G6 (Network) building

Each context is a different **game**, but they all share the same underlying mechanics:

- Signals come in (things happen)
- State accumulates (context builds)
- Transformations occur (changes happen)
- Emissions go out (observable results)

This engine is the shared foundation. Game wrappers add the semantics.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, running tests and checks, and how to submit changes. We also have a [Code of Conduct](CODE_OF_CONDUCT.md) and [Security](SECURITY.md) policy.

## License

MIT
