"""
Core types for the MetaSPN Game Engine.

These are the fundamental abstractions that all games build upon:
- Signal: Typed input event with timestamp and metadata
- Emission: Typed output event from the pipeline  
- State: Typed accumulated context between signals

All are immutable and serializable.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import TypeVar, Generic, Any, Dict, Callable
from uuid import uuid4


# Type variables for generic typing
T = TypeVar("T")  # Signal payload type
U = TypeVar("U")  # Emission payload type
S = TypeVar("S")  # State type


@dataclass(frozen=True)
class Signal(Generic[T]):
    """
    An immutable input event to the engine.
    
    Signals are the atomic unit of input. They carry:
    - A typed payload (the actual data)
    - A timestamp (when the event occurred)
    - A source identifier (where it came from)
    - Optional metadata (anything else)
    
    Subclass this to create domain-specific signal types.
    
    Example:
        @dataclass(frozen=True)
        class PodcastListenSignal(Signal[PodcastListen]):
            pass
            
        signal = PodcastListenSignal(
            payload=PodcastListen(episode_id="123", duration=3600),
            timestamp=datetime.now(),
            source="overcast"
        )
    """
    payload: T
    timestamp: datetime
    source: str
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def with_metadata(self, **kwargs) -> Signal[T]:
        """Return a new signal with additional metadata."""
        new_metadata = {**self.metadata, **kwargs}
        return Signal(
            payload=self.payload,
            timestamp=self.timestamp,
            source=self.source,
            signal_id=self.signal_id,
            metadata=new_metadata
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "payload": self._serialize_payload(),
            "metadata": self.metadata,
        }
    
    def _serialize_payload(self) -> Any:
        """Serialize payload - override for custom types."""
        if hasattr(self.payload, "to_dict"):
            return self.payload.to_dict()
        if hasattr(self.payload, "__dict__"):
            return asdict(self.payload) if hasattr(self.payload, "__dataclass_fields__") else self.payload.__dict__  # type: ignore[call-overload]
        return self.payload
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], payload_factory: Callable[[Any], T]) -> Signal[T]:
        """Deserialize from dictionary."""
        return cls(
            signal_id=data["signal_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            payload=payload_factory(data["payload"]),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class Emission(Generic[U]):
    """
    An immutable output event from the engine.
    
    Emissions are what the pipeline produces. They carry:
    - A typed payload (the computed output)
    - The signal_id that caused this emission (for traceability)
    - A timestamp (when the emission was created)
    - An emission type (for routing/filtering downstream)
    - Optional metadata
    
    Example:
        @dataclass(frozen=True)
        class ScoreUpdate(Emission[GameScore]):
            pass
            
        emission = ScoreUpdate(
            payload=GameScore(g2=0.85, g4=0.12),
            caused_by="signal_abc123",
            emission_type="score_update"
        )
    """
    payload: U
    caused_by: str  # signal_id that caused this emission
    emission_type: str
    emission_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "emission_id": self.emission_id,
            "caused_by": self.caused_by,
            "emission_type": self.emission_type,
            "timestamp": self.timestamp.isoformat(),
            "payload": self._serialize_payload(),
            "metadata": self.metadata,
        }
    
    def _serialize_payload(self) -> Any:
        """Serialize payload - override for custom types."""
        if hasattr(self.payload, "to_dict"):
            return self.payload.to_dict()
        if hasattr(self.payload, "__dict__"):
            return asdict(self.payload) if hasattr(self.payload, "__dataclass_fields__") else self.payload.__dict__  # type: ignore[call-overload]
        return self.payload


@dataclass
class State(Generic[S]):
    """
    Mutable accumulated context between signals.
    
    State is the only mutable thing in the engine. It carries:
    - A typed value (the actual state)
    - A version counter (for debugging/replay)
    - History of state transitions (optional, for debugging)
    
    Games define their own state shape. The engine manages
    state transitions through the pipeline.
    
    Example:
        @dataclass
        class GameState:
            total_signals: int = 0
            running_average: float = 0.0
            last_emission: Optional[datetime] = None
            
        state = State(value=GameState())
        state.update(GameState(total_signals=1, running_average=0.5))
    """
    value: S
    version: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    _history: list = field(default_factory=list, repr=False)
    _track_history: bool = field(default=False, repr=False)
    
    def update(self, new_value: S) -> State[S]:
        """
        Update state with new value, incrementing version.
        Returns self for chaining.
        """
        if self._track_history:
            self._history.append({
                "version": self.version,
                "value": self._snapshot_value(),
                "timestamp": self.updated_at.isoformat()
            })
        
        self.value = new_value
        self.version += 1
        self.updated_at = datetime.now()
        return self
    
    def _snapshot_value(self) -> Any:
        """Create a snapshot of the current value."""
        if hasattr(self.value, "to_dict"):
            return self.value.to_dict()
        if hasattr(self.value, "__dict__"):
            return asdict(self.value) if hasattr(self.value, "__dataclass_fields__") else dict(self.value.__dict__)  # type: ignore[call-overload]
        return self.value
    
    def get_history(self) -> list[Any]:
        """Return history of state transitions."""
        return list(self._history)
    
    def enable_history(self) -> State[S]:
        """Enable history tracking. Returns self for chaining."""
        self._track_history = True
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "value": self._snapshot_value(),
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], value_factory: Callable[[Any], S]) -> State[S]:
        """Deserialize from dictionary."""
        return cls(
            value=value_factory(data["value"]),
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


# Convenience type aliases
AnySignal = Signal[Any]
AnyEmission = Emission[Any]
AnyState = State[Any]
