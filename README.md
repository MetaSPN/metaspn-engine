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
