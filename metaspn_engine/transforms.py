"""
Common transforms for building pipelines.

These are reusable step functions that can be composed into pipelines.
All transforms are pure functions that follow the Step protocol.
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import (
    TypeVar, Any, Optional, List,
    Callable
)
from collections import deque

from .core import Signal, Emission
from .pipeline import StepResult, Predicate


T = TypeVar("T")
U = TypeVar("U")
S = TypeVar("S")


# =============================================================================
# MAP TRANSFORMS
# =============================================================================

def map_signal(
    mapper: Callable[[Any], Any],
    field: str = "payload"
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Transform signal payload.
    
    Note: Signals are immutable, so this creates metadata noting the transform.
    The mapper function is applied and result stored in metadata.
    
    Example:
        pipeline = Pipeline([
            map_signal(lambda x: x.upper(), field="normalized"),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        # Apply mapper (result not stored - use state or later steps for side effects)
        mapper(signal.payload)
        return [], None
    
    return step


def map_to_emission(
    mapper: Callable[[Any, Any], Any],
    emission_type: str,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Map signal + state to an emission.
    
    Example:
        pipeline = Pipeline([
            map_to_emission(
                mapper=lambda payload, state: {"score": compute_score(payload, state)},
                emission_type="score_computed"
            ),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        result = mapper(signal.payload, state)
        emission = Emission(
            payload=result,
            caused_by=signal.signal_id,
            emission_type=emission_type,
        )
        return [emission], None
    
    return step


# =============================================================================
# FILTER TRANSFORMS
# =============================================================================

def filter_signal(predicate: Predicate) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Filter signals - only continue processing if predicate is true.
    
    Note: This doesn't actually stop the pipeline, it just returns no emissions.
    For true filtering, use Pipeline.filter() method.
    
    Example:
        pipeline = Pipeline([
            filter_signal(lambda s: s.payload.score > 0.5),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        if predicate(signal):
            return [], None
        # Return special marker that signal was filtered
        return [], None
    
    return step


def filter_by_source(sources: List[str]) -> Callable[[Signal[Any], Any], StepResult]:
    """Filter to only allow signals from specific sources."""
    def step(signal: Signal[Any], state: Any) -> StepResult:
        if signal.source in sources:
            return [], None
        return [], None
    
    return step


# =============================================================================
# STATE TRANSFORMS
# =============================================================================

def accumulate(
    field: str,
    accumulator: Callable[[Any, Any], Any],
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Accumulate values into a state field.
    
    Example:
        pipeline = Pipeline([
            accumulate("total", lambda acc, val: acc + val.amount),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        current = getattr(state, field, None)
        new_value = accumulator(current, signal.payload)
        
        def updater(s):
            if hasattr(s, "__dataclass_fields__"):
                return replace(s, **{field: new_value})
            elif isinstance(s, dict):
                return {**s, field: new_value}
            else:
                setattr(s, field, new_value)
                return s
        
        return [], updater
    
    return step


def set_state(
    field: str,
    extractor: Callable[[Any, Any], Any],
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Set a state field based on signal payload.
    
    Example:
        pipeline = Pipeline([
            set_state("last_seen", lambda payload, state: datetime.now()),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        new_value = extractor(signal.payload, state)
        
        def updater(s):
            if hasattr(s, "__dataclass_fields__"):
                return replace(s, **{field: new_value})
            elif isinstance(s, dict):
                return {**s, field: new_value}
            else:
                setattr(s, field, new_value)
                return s
        
        return [], updater
    
    return step


def update_state(
    updater_fn: Callable[[Any, Any], Any]
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Update entire state based on signal.
    
    Example:
        pipeline = Pipeline([
            update_state(lambda payload, state: compute_new_state(payload, state)),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        new_state = updater_fn(signal.payload, state)
        return [], lambda s: new_state
    
    return step


# =============================================================================
# WINDOW TRANSFORMS
# =============================================================================

@dataclass
class WindowState:
    """State for windowed operations."""
    items: deque[Any] | None = None
    window_size: int = 10

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = deque(maxlen=self.window_size)


def window(
    size: int,
    state_field: str = "_window",
    extractor: Callable[[Any], Any] = lambda x: x,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Maintain a sliding window of values.
    
    Example:
        pipeline = Pipeline([
            window(size=10, state_field="recent_scores", extractor=lambda p: p.score),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        value = extractor(signal.payload)
        
        # Get or create window
        window_state = getattr(state, state_field, None)
        if window_state is None:
            window_state = WindowState(window_size=size)
        
        # Add to window
        existing = window_state.items if window_state.items is not None else deque(maxlen=size)
        new_items = deque(existing, maxlen=size)
        new_items.append(value)
        new_window = WindowState(items=new_items, window_size=size)
        
        def updater(s):
            if hasattr(s, "__dataclass_fields__"):
                return replace(s, **{state_field: new_window})
            elif isinstance(s, dict):
                return {**s, state_field: new_window}
            else:
                setattr(s, state_field, new_window)
                return s
        
        return [], updater
    
    return step


def time_window(
    duration: timedelta,
    state_field: str = "_time_window",
    extractor: Callable[[Any], Any] = lambda x: x,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Maintain a time-based sliding window.
    
    Example:
        pipeline = Pipeline([
            time_window(
                duration=timedelta(hours=24),
                state_field="daily_events",
            ),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        value = extractor(signal.payload)
        timestamp = signal.timestamp
        cutoff = timestamp - duration
        
        # Get existing window
        current_window = getattr(state, state_field, [])
        
        # Filter to items within duration and add new
        new_window = [
            (ts, val) for ts, val in current_window
            if ts > cutoff
        ]
        new_window.append((timestamp, value))
        
        def updater(s):
            if hasattr(s, "__dataclass_fields__"):
                return replace(s, **{state_field: new_window})
            elif isinstance(s, dict):
                return {**s, state_field: new_window}
            else:
                setattr(s, state_field, new_window)
                return s
        
        return [], updater
    
    return step


# =============================================================================
# EMISSION TRANSFORMS
# =============================================================================

def emit(
    emission_type: str,
    payload_extractor: Callable[[Any, Any], Any],
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Always emit an emission.
    
    Example:
        pipeline = Pipeline([
            emit("signal_received", lambda payload, state: {"received": True}),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        payload = payload_extractor(signal.payload, state)
        emission = Emission(
            payload=payload,
            caused_by=signal.signal_id,
            emission_type=emission_type,
        )
        return [emission], None
    
    return step


def emit_if(
    condition: Callable[[Any, Any], bool],
    emission_type: str,
    payload_extractor: Callable[[Any, Any], Any],
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Conditionally emit an emission.
    
    Example:
        pipeline = Pipeline([
            emit_if(
                condition=lambda payload, state: payload.score > 0.8,
                emission_type="high_score",
                payload_extractor=lambda payload, state: {"score": payload.score},
            ),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        if condition(signal.payload, state):
            payload = payload_extractor(signal.payload, state)
            emission = Emission(
                payload=payload,
                caused_by=signal.signal_id,
                emission_type=emission_type,
            )
            return [emission], None
        return [], None
    
    return step


def emit_on_change(
    state_field: str,
    emission_type: str,
    change_detector: Callable[[Any, Any], bool] = lambda old, new: old != new,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Emit when a state field changes.
    
    Example:
        pipeline = Pipeline([
            update_state(...),
            emit_on_change("level", "level_up"),
        ])
    """
    _previous = [None]  # Mutable container to track previous value
    
    def step(signal: Signal[Any], state: Any) -> StepResult:
        current = getattr(state, state_field, None)
        previous = _previous[0]
        _previous[0] = current
        
        if previous is not None and change_detector(previous, current):
            emission = Emission(
                payload={"old": previous, "new": current, "field": state_field},
                caused_by=signal.signal_id,
                emission_type=emission_type,
            )
            return [emission], None
        return [], None
    
    return step


# =============================================================================
# CONTROL FLOW TRANSFORMS
# =============================================================================

def branch(
    condition: Callable[[Any, Any], bool],
    if_true: Callable[[Signal[Any], Any], StepResult],
    if_false: Optional[Callable[[Signal[Any], Any], StepResult]] = None,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Branch based on condition.
    
    Example:
        pipeline = Pipeline([
            branch(
                condition=lambda payload, state: payload.type == "podcast",
                if_true=handle_podcast,
                if_false=handle_other,
            ),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        if condition(signal.payload, state):
            return if_true(signal, state)
        elif if_false is not None:
            return if_false(signal, state)
        return [], None
    
    return step


def merge(*steps: Callable[[Signal[Any], Any], StepResult]) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Run multiple steps and merge their results.
    
    All emissions are collected. State updates are applied in order.
    
    Example:
        pipeline = Pipeline([
            merge(
                compute_quality,
                compute_game_signature,
                compute_trajectory,
            ),
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        all_emissions: List[Emission[Any]] = []
        current_state = state
        
        for s in steps:
            emissions, updater = s(signal, current_state)
            all_emissions.extend(emissions)
            if updater is not None:
                current_state = updater(current_state)
        
        if current_state is not state:
            return all_emissions, lambda s: current_state
        return all_emissions, None
    
    return step


def sequence(*steps: Callable[[Signal[Any], Any], StepResult]) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Run steps in sequence, threading state through.
    
    Same as merge but makes sequential intent explicit.
    """
    return merge(*steps)


# =============================================================================
# UTILITY TRANSFORMS
# =============================================================================

def log(
    message_fn: Callable[[Any, Any], str],
    logger: Callable[[str], None] = print,
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Log signals for debugging (no-op for emissions/state).
    
    Example:
        pipeline = Pipeline([
            log(lambda p, s: f"Processing: {p}"),
            actual_processing_step,
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        message = message_fn(signal.payload, state)
        logger(message)
        return [], None
    
    return step


def tap(
    side_effect: Callable[[Any, Any], None],
) -> Callable[[Signal[Any], Any], StepResult]:
    """
    Execute a side effect without affecting pipeline.
    
    Use sparingly - side effects break purity.
    
    Example:
        pipeline = Pipeline([
            tap(lambda p, s: metrics.increment("signals_processed")),
            actual_processing_step,
        ])
    """
    def step(signal: Signal[Any], state: Any) -> StepResult:
        side_effect(signal.payload, state)
        return [], None
    
    return step


def identity() -> Callable[[Signal[Any], Any], StepResult]:
    """No-op step. Useful for conditional pipeline building."""
    def step(signal: Signal[Any], state: Any) -> StepResult:
        return [], None
    return step
