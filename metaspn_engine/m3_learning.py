"""Reference M3 attempt/outcome/failure/calibration learning pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .core import Emission, Signal
from .pipeline import Pipeline, StepResult


@dataclass(frozen=True)
class M3AttemptSignal:
    """Minimal learning-attempt payload aligned with M3 stage boundaries."""

    learner_id: str
    skill_id: str
    attempt_id: str
    expected_score: float
    observed_score: float


@dataclass
class M3LearningState:
    """State threaded through attempt -> calibration processing."""

    attempts_seen: int = 0
    outcomes_emitted: int = 0
    failures_emitted: int = 0
    calibrations_emitted: int = 0
    latest_gap: float = 0.0
    latest_failure_class: str = ""


def _attempt_stage(signal: Signal[M3AttemptSignal], state: M3LearningState) -> StepResult:
    emission = Emission(
        emission_id=f"{signal.signal_id}:attempt",
        emission_type="m3.attempt.snapshot",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "learner_id": signal.payload.learner_id,
            "skill_id": signal.payload.skill_id,
            "attempt_id": signal.payload.attempt_id,
            "expected_score": signal.payload.expected_score,
            "observed_score": signal.payload.observed_score,
        },
    )
    return [emission], None


def _outcome_stage(signal: Signal[M3AttemptSignal], state: M3LearningState) -> StepResult:
    gap = round(signal.payload.expected_score - signal.payload.observed_score, 4)
    passed = signal.payload.observed_score >= signal.payload.expected_score
    emission = Emission(
        emission_id=f"{signal.signal_id}:outcome",
        emission_type="m3.outcome.evaluated",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "attempt_id": signal.payload.attempt_id,
            "passed": passed,
            "gap": gap,
        },
    )

    def updater(_: M3LearningState) -> M3LearningState:
        return M3LearningState(
            attempts_seen=state.attempts_seen + 1,
            outcomes_emitted=state.outcomes_emitted + 1,
            failures_emitted=state.failures_emitted,
            calibrations_emitted=state.calibrations_emitted,
            latest_gap=gap,
            latest_failure_class=state.latest_failure_class,
        )

    return [emission], updater


def _failure_stage(signal: Signal[M3AttemptSignal], state: M3LearningState) -> StepResult:
    gap = state.latest_gap
    failure_class = "none" if gap <= 0 else ("minor_gap" if gap < 0.1 else "major_gap")
    emission = Emission(
        emission_id=f"{signal.signal_id}:failure",
        emission_type="m3.failure.classified",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "attempt_id": signal.payload.attempt_id,
            "failure_class": failure_class,
            "gap": gap,
        },
    )

    def updater(_: M3LearningState) -> M3LearningState:
        return M3LearningState(
            attempts_seen=state.attempts_seen,
            outcomes_emitted=state.outcomes_emitted,
            failures_emitted=state.failures_emitted + 1,
            calibrations_emitted=state.calibrations_emitted,
            latest_gap=state.latest_gap,
            latest_failure_class=failure_class,
        )

    return [emission], updater


def _calibration_stage(signal: Signal[M3AttemptSignal], state: M3LearningState) -> StepResult:
    proposal = "maintain" if state.latest_failure_class == "none" else "increase_support"
    if state.latest_failure_class == "major_gap":
        proposal = "rebuild_foundation"
    emission = Emission(
        emission_id=f"{signal.signal_id}:calibration",
        emission_type="m3.calibration.proposed",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "attempt_id": signal.payload.attempt_id,
            "proposal": proposal,
            "failure_class": state.latest_failure_class,
        },
    )

    def updater(_: M3LearningState) -> M3LearningState:
        return M3LearningState(
            attempts_seen=state.attempts_seen,
            outcomes_emitted=state.outcomes_emitted,
            failures_emitted=state.failures_emitted,
            calibrations_emitted=state.calibrations_emitted + 1,
            latest_gap=state.latest_gap,
            latest_failure_class=state.latest_failure_class,
        )

    return [emission], updater


def build_m3_learning_pipeline() -> Pipeline:
    """Create deterministic attempt -> outcome -> failure -> calibration flow."""

    return Pipeline(
        steps=[_attempt_stage, _outcome_stage, _failure_stage, _calibration_stage],
        name="m3_attempt_outcome_failure_calibration",
    )


def make_m3_signal(
    *,
    signal_id: str,
    timestamp: datetime,
    source: str,
    learner_id: str,
    skill_id: str,
    attempt_id: str,
    expected_score: float,
    observed_score: float,
) -> Signal[M3AttemptSignal]:
    """Construct stable-ID M3 learning signals for reference orchestration."""

    return Signal(
        signal_id=signal_id,
        timestamp=timestamp,
        source=source,
        payload=M3AttemptSignal(
            learner_id=learner_id,
            skill_id=skill_id,
            attempt_id=attempt_id,
            expected_score=expected_score,
            observed_score=observed_score,
        ),
    )
