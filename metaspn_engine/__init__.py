"""
MetaSPN Game Engine - Minimal Core

A pure signal processing engine for building observable games.
Zero game semantics - only typed signals, transformations, and state.

Usage:
    from metaspn_engine import Signal, Pipeline, Engine
    
    # Define your signal type
    @dataclass
    class MySignal(Signal):
        value: float
        
    # Build a pipeline
    pipeline = Pipeline([
        normalize,
        detect_anomalies,
        emit_if_significant
    ])
    
    # Run engine
    engine = Engine(pipeline, initial_state={})
    for signal in signals:
        emissions = engine.process(signal)
"""

from .core import Signal, Emission, State
from .pipeline import Pipeline, Step, Predicate
from .engine import Engine
from .transforms import (
    map_signal,
    filter_signal,
    accumulate,
    window,
    emit,
    emit_if,
    branch,
    merge,
)
from .protocols import GameProtocol, SignalSource, EmissionSink

__version__ = "0.1.0"
__all__ = [
    # Core types
    "Signal",
    "Emission", 
    "State",
    # Pipeline
    "Pipeline",
    "Step",
    "Predicate",
    # Engine
    "Engine",
    # Transforms
    "map_signal",
    "filter_signal",
    "accumulate",
    "window",
    "emit",
    "emit_if",
    "branch",
    "merge",
    # Protocols
    "GameProtocol",
    "SignalSource",
    "EmissionSink",
]
