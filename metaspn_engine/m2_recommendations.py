"""Reference M2 score/context -> recommendation -> draft emission pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from .core import Emission, Signal
from .pipeline import Pipeline, StepResult


@dataclass(frozen=True)
class RecommendationCandidate:
    """Candidate item for M2 recommendation ranking."""

    candidate_id: str
    title: str
    score: float
    context_boost: float = 0.0


@dataclass(frozen=True)
class M2RecommendationSignal:
    """M2 input payload carrying candidates and prompt context."""

    audience_id: str
    prompt: str
    candidates: tuple[RecommendationCandidate, ...]


@dataclass
class M2RecommendationState:
    """State used across ranking and draft shaping stages."""

    ranked_count: int = 0
    drafted_count: int = 0
    latest_top_candidate_id: str = ""
    latest_ranked_ids: List[str] = field(default_factory=list)


def _rank_stage(signal: Signal[M2RecommendationSignal], state: M2RecommendationState) -> StepResult:
    # Bucket the blended score so near-equal values sort deterministically by candidate_id.
    ranked = sorted(
        signal.payload.candidates,
        key=lambda candidate: (
            -round(candidate.score + candidate.context_boost, 3),
            candidate.candidate_id,
        ),
    )
    ranked_ids = [item.candidate_id for item in ranked]
    top = ranked[0]

    emission = Emission(
        emission_id=f"{signal.signal_id}:recommendation",
        emission_type="m2.recommendation.ranked",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "audience_id": signal.payload.audience_id,
            "ranked_ids": ranked_ids,
            "top_candidate_id": top.candidate_id,
        },
    )

    def updater(_: M2RecommendationState) -> M2RecommendationState:
        return M2RecommendationState(
            ranked_count=state.ranked_count + 1,
            drafted_count=state.drafted_count,
            latest_top_candidate_id=top.candidate_id,
            latest_ranked_ids=ranked_ids,
        )

    return [emission], updater


def _draft_stage(signal: Signal[M2RecommendationSignal], state: M2RecommendationState) -> StepResult:
    if not state.latest_top_candidate_id:
        return [], None

    top = next(item for item in signal.payload.candidates if item.candidate_id == state.latest_top_candidate_id)
    emission = Emission(
        emission_id=f"{signal.signal_id}:draft",
        emission_type="m2.draft.generated",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "audience_id": signal.payload.audience_id,
            "recommended_candidate_id": top.candidate_id,
            "draft_text": f"{signal.payload.prompt}: {top.title}",
        },
    )

    def updater(_: M2RecommendationState) -> M2RecommendationState:
        return M2RecommendationState(
            ranked_count=state.ranked_count,
            drafted_count=state.drafted_count + 1,
            latest_top_candidate_id=state.latest_top_candidate_id,
            latest_ranked_ids=list(state.latest_ranked_ids),
        )

    return [emission], updater


def build_m2_recommendation_pipeline() -> Pipeline:
    """Create deterministic M2 ranking -> draft emission composition."""

    return Pipeline(
        steps=[_rank_stage, _draft_stage],
        name="m2_rank_and_draft",
    )


def make_m2_signal(
    *,
    signal_id: str,
    timestamp: datetime,
    source: str,
    audience_id: str,
    prompt: str,
    candidates: tuple[RecommendationCandidate, ...],
) -> Signal[M2RecommendationSignal]:
    """Construct stable-ID M2 signals for reference orchestration."""

    return Signal(
        signal_id=signal_id,
        timestamp=timestamp,
        source=source,
        payload=M2RecommendationSignal(
            audience_id=audience_id,
            prompt=prompt,
            candidates=candidates,
        ),
    )
