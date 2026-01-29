"""
Pipeline abstraction for the MetaSPN Game Engine.

A Pipeline is a sequence of Steps that process signals.
Steps are pure functions that take (signal, state) and return (emissions, state_updates).

Pipelines are composable and can be nested.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import (
    Any, Optional, List, 
    Callable, Tuple, Protocol
)

from .core import Signal, Emission, State


# A predicate is a function that takes a signal and returns bool
Predicate = Callable[[Signal[Any]], bool]

# Step result: list of emissions and optional state update function
StepResult = Tuple[List[Emission[Any]], Optional[Callable[[Any], Any]]]


class Step(Protocol):
    """
    Protocol for a pipeline step.
    
    A step is a pure function that processes a signal given current state,
    and returns emissions plus an optional state updater.
    
    Steps should be:
    - Pure (no side effects except through state updates)
    - Composable (can be chained)
    - Testable (given signal + state, output is deterministic)
    """
    
    def __call__(
        self,
        signal: Signal[Any],
        state: Any,
    ) -> StepResult:
        """
        Process a signal.
        
        Args:
            signal: The input signal to process
            state: Current state value (not the State wrapper)
            
        Returns:
            Tuple of:
            - List of emissions (can be empty)
            - Optional state update function: (old_state) -> new_state
              If None, state is unchanged.
        """
        ...


@dataclass
class Pipeline:
    """
    A sequence of steps that process signals.
    
    Pipelines are the core abstraction for building games.
    They chain steps together, threading state through each step.
    
    Example:
        pipeline = Pipeline([
            extract_features,
            compute_score,
            emit_if_threshold,
        ])
        
        emissions, final_state = pipeline.process(signal, state)
    """
    steps: List[Step]
    name: str = "unnamed"
    
    def process(
        self, 
        signal: Signal[Any], 
        state: State[Any]
    ) -> Tuple[List[Emission[Any]], State[Any]]:
        """
        Process a signal through all steps.
        
        Args:
            signal: Input signal
            state: Current state wrapper
            
        Returns:
            Tuple of all emissions and updated state
        """
        all_emissions: List[Emission[Any]] = []
        current_state_value = state.value
        
        for step in self.steps:
            emissions, state_updater = step(signal, current_state_value)
            all_emissions.extend(emissions)
            
            if state_updater is not None:
                current_state_value = state_updater(current_state_value)
        
        # Apply final state update
        if current_state_value is not state.value:
            state.update(current_state_value)
        
        return all_emissions, state
    
    def then(self, step: Step) -> Pipeline:
        """Add a step to the pipeline. Returns new pipeline."""
        return Pipeline(
            steps=self.steps + [step],
            name=self.name
        )
    
    def branch(
        self,
        predicate: Predicate,
        if_true: Pipeline,
        if_false: Optional[Pipeline] = None
    ) -> Pipeline:
        """
        Add conditional branching to the pipeline.
        
        Args:
            predicate: Function that takes signal and returns bool
            if_true: Pipeline to run if predicate is true
            if_false: Optional pipeline to run if predicate is false
            
        Returns:
            New pipeline with branching step appended
        """
        def branch_step(signal: Signal[Any], state: Any) -> StepResult:
            if predicate(signal):
                # Create temporary state wrapper for sub-pipeline
                temp_state = State(value=state)
                emissions, _ = if_true.process(signal, temp_state)

                def state_update(s: Any) -> Any:
                    return temp_state.value

                return emissions, state_update
            elif if_false is not None:
                temp_state = State(value=state)
                emissions, _ = if_false.process(signal, temp_state)

                def state_update(s: Any) -> Any:
                    return temp_state.value

                return emissions, state_update
            else:
                return [], None
        
        return self.then(branch_step)
    
    def filter(self, predicate: Predicate) -> Pipeline:
        """
        Add a filter step - only continue if predicate is true.
        """
        def filter_step(signal: Signal[Any], state: Any) -> StepResult:
            if predicate(signal):
                # Pass through (no emissions, no state change at filter)
                return [], None
            else:
                # Signal "stop" by returning special marker
                # Actually, we need to handle this differently...
                # For now, just return empty
                return [], None
        
        # Actually, filtering needs to be handled at pipeline level
        # Let's create a FilteredPipeline instead
        return FilteredPipeline(
            steps=self.steps,
            name=self.name,
            filter_predicate=predicate
        )
    
    def __add__(self, other: Pipeline) -> Pipeline:
        """Concatenate two pipelines."""
        return Pipeline(
            steps=self.steps + other.steps,
            name=f"{self.name}+{other.name}"
        )


@dataclass
class FilteredPipeline(Pipeline):
    """Pipeline that only processes signals matching a predicate."""
    
    filter_predicate: Predicate = field(default=lambda s: True)
    
    def process(
        self,
        signal: Signal[Any],
        state: State[Any]
    ) -> Tuple[List[Emission[Any]], State[Any]]:
        """Process signal only if it passes the filter."""
        if not self.filter_predicate(signal):
            return [], state
        return super().process(signal, state)


@dataclass
class ParallelPipeline:
    """
    Run multiple pipelines in parallel on the same signal.
    
    All pipelines see the same input state.
    Emissions are collected from all pipelines.
    State updates are merged (last write wins for conflicts).
    
    Example:
        parallel = ParallelPipeline([
            quality_pipeline,
            game_signature_pipeline,
            trajectory_pipeline,
        ])
    """
    pipelines: List[Pipeline]
    name: str = "parallel"
    
    def process(
        self,
        signal: Signal[Any],
        state: State[Any]
    ) -> Tuple[List[Emission[Any]], State[Any]]:
        """Process signal through all pipelines in parallel."""
        all_emissions: List[Emission[Any]] = []
        
        # Each pipeline gets a copy of state value to work with
        # Final state is merged
        state_values = []
        
        for pipeline in self.pipelines:
            # Create independent state wrapper
            pipe_state = State(value=state.value)
            emissions, _ = pipeline.process(signal, pipe_state)
            all_emissions.extend(emissions)
            state_values.append(pipe_state.value)
        
        # Merge states - for now, simple last-write-wins
        # Games can implement custom merge logic
        if state_values:
            final_value = self._merge_states(state.value, state_values)
            if final_value is not state.value:
                state.update(final_value)
        
        return all_emissions, state
    
    def _merge_states(self, original: Any, updates: List[Any]) -> Any:
        """
        Merge multiple state updates.
        
        Default: last update wins entirely.
        Override for custom merge logic.
        """
        if not updates:
            return original
        
        # If state is a dataclass, merge fields
        if hasattr(original, "__dataclass_fields__"):
            from dataclasses import fields, replace
            merged = original
            for update in updates:
                # Merge non-None fields from update
                for f in fields(update):
                    update_val = getattr(update, f.name)
                    if update_val is not None:
                        merged = replace(merged, **{f.name: update_val})
            return merged
        
        # Otherwise, last write wins
        return updates[-1]


# Convenience function for creating pipelines
def pipeline(*steps: Step, name: str = "unnamed") -> Pipeline:
    """Create a pipeline from steps."""
    return Pipeline(steps=list(steps), name=name)
