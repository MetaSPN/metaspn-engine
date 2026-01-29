"""
Engine - The runtime for processing signals through pipelines.

The Engine is the main entry point for running games. It:
- Accepts signals from sources
- Processes them through pipelines
- Manages state persistence
- Delivers emissions to sinks
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any, Optional, List,
    Callable, Iterator, Iterable, Tuple
)
import json
from pathlib import Path

from .core import Signal, Emission, State
from .pipeline import Pipeline


@dataclass
class EngineConfig:
    """Configuration for the engine."""
    
    # State persistence
    persist_state: bool = True
    state_file: Optional[Path] = None
    
    # History tracking
    track_signal_history: bool = False
    track_emission_history: bool = True
    max_history_size: int = 1000
    
    # Processing
    batch_size: int = 100
    
    # Hooks
    on_signal: Optional[Callable[[Signal[Any]], None]] = None
    on_emission: Optional[Callable[[Emission[Any]], None]] = None
    on_state_change: Optional[Callable[[Any, Any], None]] = None
    on_error: Optional[Callable[[Exception, Signal[Any]], None]] = None


@dataclass
class EngineStats:
    """Runtime statistics for the engine."""
    signals_processed: int = 0
    emissions_produced: int = 0
    errors_encountered: int = 0
    state_updates: int = 0
    started_at: Optional[datetime] = None
    last_signal_at: Optional[datetime] = None
    last_emission_at: Optional[datetime] = None


class Engine:
    """
    The runtime for processing signals through pipelines.
    
    Example:
        # Create engine with pipeline and initial state
        engine = Engine(
            pipeline=my_pipeline,
            initial_state=MyGameState(),
        )
        
        # Process signals
        for signal in signal_source:
            emissions = engine.process(signal)
            for emission in emissions:
                handle_emission(emission)
        
        # Or process a batch
        all_emissions = engine.process_batch(signals)
        
        # Get final state
        final_state = engine.state.value
    """
    
    def __init__(
        self,
        pipeline: Pipeline,
        initial_state: Any,
        config: Optional[EngineConfig] = None,
    ):
        """
        Initialize the engine.
        
        Args:
            pipeline: The pipeline to process signals through
            initial_state: Initial state value (not wrapped)
            config: Optional engine configuration
        """
        self.pipeline = pipeline
        self.state = State(value=initial_state)
        self.config = config or EngineConfig()
        self.stats = EngineStats()
        
        # History buffers
        self._signal_history: List[Signal[Any]] = []
        self._emission_history: List[Emission[Any]] = []
        
        # Load persisted state if configured
        if self.config.persist_state and self.config.state_file:
            self._load_state()
    
    def process(self, signal: Signal[Any]) -> List[Emission[Any]]:
        """
        Process a single signal through the pipeline.
        
        Args:
            signal: The signal to process
            
        Returns:
            List of emissions produced
        """
        # Update stats
        self.stats.signals_processed += 1
        self.stats.last_signal_at = datetime.now()
        if self.stats.started_at is None:
            self.stats.started_at = datetime.now()
        
        # Track signal if configured
        if self.config.track_signal_history:
            self._add_to_history(self._signal_history, signal)
        
        # Call signal hook
        if self.config.on_signal:
            self.config.on_signal(signal)
        
        # Capture state before for change detection
        state_before = self.state.version
        
        try:
            # Process through pipeline
            emissions, self.state = self.pipeline.process(signal, self.state)
            
            # Check for state change
            if self.state.version > state_before:
                self.stats.state_updates += 1
                if self.config.on_state_change:
                    self.config.on_state_change(state_before, self.state.value)
                
                # Persist state if configured
                if self.config.persist_state and self.config.state_file:
                    self._save_state()
            
            # Track emissions
            self.stats.emissions_produced += len(emissions)
            if emissions:
                self.stats.last_emission_at = datetime.now()
            
            if self.config.track_emission_history:
                for emission in emissions:
                    self._add_to_history(self._emission_history, emission)
            
            # Call emission hooks
            if self.config.on_emission:
                for emission in emissions:
                    self.config.on_emission(emission)
            
            return emissions
            
        except Exception as e:
            self.stats.errors_encountered += 1
            if self.config.on_error:
                self.config.on_error(e, signal)
            raise
    
    def process_batch(
        self, 
        signals: Iterable[Signal[Any]]
    ) -> List[Emission[Any]]:
        """
        Process multiple signals.
        
        Args:
            signals: Iterable of signals to process
            
        Returns:
            List of all emissions produced
        """
        all_emissions: List[Emission[Any]] = []
        for signal in signals:
            emissions = self.process(signal)
            all_emissions.extend(emissions)
        return all_emissions
    
    def stream(
        self,
        signals: Iterator[Signal[Any]]
    ) -> Iterator[Tuple[Signal[Any], List[Emission[Any]]]]:
        """
        Process signals as a stream, yielding (signal, emissions) pairs.
        
        Args:
            signals: Iterator of signals
            
        Yields:
            Tuples of (signal, emissions_for_that_signal)
        """
        for signal in signals:
            emissions = self.process(signal)
            yield signal, emissions
    
    def get_state(self) -> Any:
        """Get current state value."""
        return self.state.value
    
    def get_signal_history(self) -> List[Signal[Any]]:
        """Get signal history (if tracking enabled)."""
        return list(self._signal_history)
    
    def get_emission_history(self) -> List[Emission[Any]]:
        """Get emission history (if tracking enabled)."""
        return list(self._emission_history)
    
    def reset_state(self, new_state: Any) -> None:
        """Reset state to a new value."""
        self.state = State(value=new_state)
        if self.config.persist_state and self.config.state_file:
            self._save_state()
    
    def _add_to_history(self, history: list, item: Any) -> None:
        """Add item to history, respecting max size."""
        history.append(item)
        if len(history) > self.config.max_history_size:
            history.pop(0)
    
    def _save_state(self) -> None:
        """Save state to file."""
        if self.config.state_file:
            self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.state_file, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2, default=str)
    
    def _load_state(self) -> None:
        """Load state from file if it exists."""
        if self.config.state_file and self.config.state_file.exists():
            with open(self.config.state_file, "r") as f:
                data = json.load(f)
                # Note: This requires the state value to be JSON-serializable
                # Games should provide their own deserialization
                self.state.value = data.get("value", self.state.value)
                self.state.version = data.get("version", 0)


class EngineBuilder:
    """
    Fluent builder for creating engines.
    
    Example:
        engine = (EngineBuilder()
            .with_pipeline(my_pipeline)
            .with_initial_state(MyState())
            .with_state_file("./state.json")
            .with_emission_hook(handle_emission)
            .build())
    """
    
    def __init__(self):
        self._pipeline: Optional[Pipeline] = None
        self._initial_state: Any = None
        self._config = EngineConfig()
    
    def with_pipeline(self, pipeline: Pipeline) -> EngineBuilder:
        """Set the pipeline."""
        self._pipeline = pipeline
        return self
    
    def with_initial_state(self, state: Any) -> EngineBuilder:
        """Set the initial state."""
        self._initial_state = state
        return self
    
    def with_state_file(self, path: str) -> EngineBuilder:
        """Enable state persistence to file."""
        self._config.persist_state = True
        self._config.state_file = Path(path)
        return self
    
    def with_signal_tracking(self, enabled: bool = True) -> EngineBuilder:
        """Enable/disable signal history tracking."""
        self._config.track_signal_history = enabled
        return self
    
    def with_emission_tracking(self, enabled: bool = True) -> EngineBuilder:
        """Enable/disable emission history tracking."""
        self._config.track_emission_history = enabled
        return self
    
    def with_signal_hook(
        self, 
        hook: Callable[[Signal[Any]], None]
    ) -> EngineBuilder:
        """Add a signal processing hook."""
        self._config.on_signal = hook
        return self
    
    def with_emission_hook(
        self,
        hook: Callable[[Emission[Any]], None]
    ) -> EngineBuilder:
        """Add an emission processing hook."""
        self._config.on_emission = hook
        return self
    
    def with_error_hook(
        self,
        hook: Callable[[Exception, Signal[Any]], None]
    ) -> EngineBuilder:
        """Add an error handling hook."""
        self._config.on_error = hook
        return self
    
    def build(self) -> Engine:
        """Build the engine."""
        if self._pipeline is None:
            raise ValueError("Pipeline is required")
        if self._initial_state is None:
            raise ValueError("Initial state is required")
        
        return Engine(
            pipeline=self._pipeline,
            initial_state=self._initial_state,
            config=self._config,
        )
