"""Reference M1 profile -> score -> route composition for deterministic traces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .core import Emission, Signal
from .pipeline import Pipeline, StepResult


@dataclass(frozen=True)
class M1ProfileSignal:
    """Minimal M1 profile payload aligned to stage boundaries."""

    profile_id: str
    profile_tier: str
    quality_score: float
    intent_score: float
    channel: str


@dataclass
class M1RoutingState:
    """State shared across M1 profile/score/route stages."""

    profiled_count: int = 0
    scored_count: int = 0
    routed_count: int = 0
    last_route: str = ""


def _profile_stage(signal: Signal[M1ProfileSignal], state: M1RoutingState) -> StepResult:
    emission = Emission(
        emission_id=f"{signal.signal_id}:profile",
        emission_type="m1.profile.enriched",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "profile_id": signal.payload.profile_id,
            "profile_tier": signal.payload.profile_tier,
            "channel": signal.payload.channel,
        },
    )
    return [emission], None


def _score_stage(signal: Signal[M1ProfileSignal], state: M1RoutingState) -> StepResult:
    score = round((signal.payload.quality_score * 0.6) + (signal.payload.intent_score * 0.4), 4)
    route = "priority_review" if score >= 0.75 else "standard_queue"
    emission = Emission(
        emission_id=f"{signal.signal_id}:score",
        emission_type="m1.scores.computed",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "profile_id": signal.payload.profile_id,
            "score": score,
            "route_hint": route,
        },
    )

    def updater(_: M1RoutingState) -> M1RoutingState:
        return M1RoutingState(
            profiled_count=state.profiled_count + 1,
            scored_count=state.scored_count + 1,
            routed_count=state.routed_count,
            last_route=route,
        )

    return [emission], updater


def _route_stage(signal: Signal[M1ProfileSignal], state: M1RoutingState) -> StepResult:
    emission = Emission(
        emission_id=f"{signal.signal_id}:route",
        emission_type="m1.route.selected",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "profile_id": signal.payload.profile_id,
            "route": state.last_route,
        },
    )

    def updater(_: M1RoutingState) -> M1RoutingState:
        return M1RoutingState(
            profiled_count=state.profiled_count,
            scored_count=state.scored_count,
            routed_count=state.routed_count + 1,
            last_route=state.last_route,
        )

    return [emission], updater


def build_m1_routing_pipeline() -> Pipeline:
    """Create deterministic M1 profile -> score -> route composition."""

    return Pipeline(
        steps=[_profile_stage, _score_stage, _route_stage],
        name="m1_profile_score_route",
    )


def make_m1_signal(
    *,
    signal_id: str,
    timestamp: datetime,
    source: str,
    profile_id: str,
    profile_tier: str,
    quality_score: float,
    intent_score: float,
    channel: str,
) -> Signal[M1ProfileSignal]:
    """Construct a stable-ID signal for M1 orchestration fixtures."""

    return Signal(
        signal_id=signal_id,
        timestamp=timestamp,
        source=source,
        payload=M1ProfileSignal(
            profile_id=profile_id,
            profile_tier=profile_tier,
            quality_score=quality_score,
            intent_score=intent_score,
            channel=channel,
        ),
    )
