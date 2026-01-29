"""
Protocols for the MetaSPN Game Engine.

These are the interfaces that game implementations follow.
Using Protocol (structural subtyping) rather than ABC (nominal subtyping)
for maximum flexibility.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import (
    TypeVar, Any, Optional, Dict, List,
    Iterator, Protocol, runtime_checkable
)

from .core import Signal, Emission
from .pipeline import Pipeline


T = TypeVar("T")
U = TypeVar("U")
S = TypeVar("S")


# =============================================================================
# GAME PROTOCOL
# =============================================================================

@runtime_checkable
class GameProtocol(Protocol[T, U, S]):  # type: ignore[misc]
    """
    Protocol for implementing a game on the MetaSPN engine.
    
    A Game defines:
    - Signal types it accepts
    - State shape it maintains
    - Pipeline for processing
    - Emission types it produces
    
    Example implementation:
    
        class PodcastGame:
            name = "podcast"
            version = "1.0.0"
            
            def create_signal(self, data: dict) -> Signal[PodcastListen]:
                return Signal(
                    payload=PodcastListen(**data),
                    timestamp=datetime.now(),
                    source="overcast"
                )
            
            def initial_state(self) -> PodcastState:
                return PodcastState()
            
            def pipeline(self) -> Pipeline:
                return Pipeline([
                    track_listening,
                    compute_influence,
                    emit_if_significant,
                ])
    """
    
    name: str
    version: str
    
    def create_signal(self, data: Any) -> Signal[T]:
        """Create a signal from raw input data."""
        ...
    
    def initial_state(self) -> S:
        """Return the initial state for this game."""
        ...
    
    def pipeline(self) -> Pipeline:
        """Return the processing pipeline for this game."""
        ...
    
    def validate_signal(self, signal: Signal[T]) -> bool:
        """Validate that a signal is well-formed. Default: always valid."""
        ...
    
    def on_emission(self, emission: Emission[U]) -> None:
        """Handle an emission. Default: no-op."""
        ...


# =============================================================================
# SOURCE AND SINK PROTOCOLS
# =============================================================================

@runtime_checkable
class SignalSource(Protocol[T]):
    """
    Protocol for signal sources.
    
    Sources produce signals from external data (files, APIs, etc.)
    
    Example:
        class JSONLSource:
            def __init__(self, filepath: str):
                self.filepath = filepath
            
            def signals(self) -> Iterator[Signal[dict]]:
                with open(self.filepath) as f:
                    for line in f:
                        data = json.loads(line)
                        yield Signal(
                            payload=data,
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            source=self.filepath
                        )
    """
    
    def signals(self) -> Iterator[Signal[T]]:
        """Yield signals from the source."""
        ...


@runtime_checkable
class EmissionSink(Protocol[U]):
    """
    Protocol for emission sinks.
    
    Sinks consume emissions and do something with them
    (write to file, send to API, update UI, etc.)
    
    Example:
        class JSONLSink:
            def __init__(self, filepath: str):
                self.file = open(filepath, "a")
            
            def receive(self, emission: Emission[Any]) -> None:
                self.file.write(json.dumps(emission.to_dict()) + "\\n")
                self.file.flush()
            
            def close(self) -> None:
                self.file.close()
    """
    
    def receive(self, emission: Emission[U]) -> None:
        """Receive an emission."""
        ...
    
    def close(self) -> None:
        """Clean up resources."""
        ...


# =============================================================================
# STATE PERSISTENCE PROTOCOLS
# =============================================================================

@runtime_checkable
class StateStore(Protocol[S]):
    """
    Protocol for state persistence.
    
    Example:
        class FileStateStore:
            def __init__(self, filepath: str):
                self.filepath = filepath
            
            def load(self) -> Optional[S]:
                if os.path.exists(self.filepath):
                    with open(self.filepath) as f:
                        return json.load(f)
                return None
            
            def save(self, state: S) -> None:
                with open(self.filepath, "w") as f:
                    json.dump(state, f)
    """
    
    def load(self) -> Optional[S]:
        """Load state from storage."""
        ...
    
    def save(self, state: S) -> None:
        """Save state to storage."""
        ...


# =============================================================================
# ANALYZER PROTOCOLS
# =============================================================================

@runtime_checkable
class Analyzer(Protocol[T, U]):  # type: ignore[misc]
    """
    Protocol for analyzers that compute metrics from state/signals.
    
    Analyzers are stateless - they take input and produce output.
    They don't participate in the pipeline directly but can be
    composed into steps.
    
    Example:
        class QualityAnalyzer:
            def analyze(self, data: List[Episode]) -> QualityScore:
                # Compute quality from episodes
                return QualityScore(...)
    """
    
    def analyze(self, data: T) -> U:
        """Analyze data and return result."""
        ...


@runtime_checkable
class Scorer(Protocol):
    """
    Protocol for game scoring.
    
    Scorers compute game-specific scores from state.
    
    Example:
        class G2Scorer:
            def score(self, state: CreatorState) -> GameScore:
                return GameScore(
                    game="G2",
                    value=compute_g2_score(state),
                    components={...}
                )
    """
    
    def score(self, state: Any) -> Any:
        """Compute score from state."""
        ...


# =============================================================================
# CONNECTOR PROTOCOLS
# =============================================================================

@runtime_checkable
class Connector(Protocol):
    """
    Protocol for connecting games together.
    
    Connectors route emissions from one game to signals for another,
    enabling game composition.
    
    Example:
        class PodcastToCreatorConnector:
            def connect(self, emission: PodcastEmission) -> Optional[Signal[CreatorSignal]]:
                if emission.emission_type == "influence_detected":
                    return Signal(
                        payload=CreatorSignal(influence=emission.payload),
                        timestamp=emission.timestamp,
                        source="podcast_game"
                    )
                return None
    """
    
    def connect(self, emission: Emission[Any]) -> Optional[Signal[Any]]:
        """Convert an emission to a signal for another game."""
        ...


# =============================================================================
# VALIDATION PROTOCOLS
# =============================================================================

@runtime_checkable
class Validator(Protocol[T]):  # type: ignore[misc]
    """
    Protocol for validating signals or data.
    
    Example:
        class PodcastSignalValidator:
            def validate(self, data: PodcastListen) -> ValidationResult:
                errors = []
                if not data.episode_id:
                    errors.append("episode_id is required")
                if data.duration < 0:
                    errors.append("duration must be positive")
                return ValidationResult(valid=len(errors) == 0, errors=errors)
    """
    
    def validate(self, data: T) -> Any:
        """Validate data and return result."""
        ...


# =============================================================================
# UTILITY CLASSES
# =============================================================================

@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    errors: List[str] | None = None
    warnings: List[str] | None = None

    def __post_init__(self) -> None:
        self.errors = self.errors or []
        self.warnings = self.warnings or []


@dataclass
class GameScore:
    """A score computed by a game."""
    game: str  # G1, G2, etc.
    value: float  # 0.0 - 1.0
    components: Dict[str, float] | None = None
    computed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.components = self.components or {}
        self.computed_at = self.computed_at or datetime.now()


@dataclass
class GameSignature:
    """Distribution across all six games."""
    G1: float = 0.0  # Identity/Canon
    G2: float = 0.0  # Idea Mining
    G3: float = 0.0  # Models
    G4: float = 0.0  # Performance
    G5: float = 0.0  # Meaning
    G6: float = 0.0  # Network
    
    def primary_game(self) -> str:
        """Return the dominant game."""
        games = {"G1": self.G1, "G2": self.G2, "G3": self.G3, 
                 "G4": self.G4, "G5": self.G5, "G6": self.G6}
        return max(games, key=lambda k: games[k])
    
    def is_specialist(self, threshold: float = 0.6) -> bool:
        """True if any game exceeds threshold."""
        return any(v > threshold for v in 
                   [self.G1, self.G2, self.G3, self.G4, self.G5, self.G6])
    
    def normalize(self) -> GameSignature:
        """Return normalized signature (sums to 1.0)."""
        total = self.G1 + self.G2 + self.G3 + self.G4 + self.G5 + self.G6
        if total == 0:
            return self
        return GameSignature(
            G1=self.G1/total, G2=self.G2/total, G3=self.G3/total,
            G4=self.G4/total, G5=self.G5/total, G6=self.G6/total,
        )
