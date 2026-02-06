"""Reference M0 ingestion orchestration flow built on top of the engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .core import Emission, Signal
from .pipeline import Pipeline, StepResult


@dataclass(frozen=True)
class SocialIngestionEvent:
    """Minimal social ingestion payload for M0 reference flows."""

    platform: str
    external_id: str
    actor_ref: str
    content_hash: str


@dataclass
class M0IngestionState:
    """State carried across M0 ingest -> resolve -> emit processing."""

    ingested_count: int = 0
    resolved_count: int = 0
    last_entity_ref: str = ""


def _ingest_step(signal: Signal[SocialIngestionEvent], state: M0IngestionState) -> StepResult:
    emission = Emission(
        emission_id=f"{signal.signal_id}:ingest",
        emission_type="m0.ingest.accepted",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "platform": signal.payload.platform,
            "external_id": signal.payload.external_id,
            "content_hash": signal.payload.content_hash,
        },
    )
    return [emission], None


def _resolve_step(signal: Signal[SocialIngestionEvent], state: M0IngestionState) -> StepResult:
    entity_ref = f"{signal.payload.platform}:{signal.payload.actor_ref}"
    emission = Emission(
        emission_id=f"{signal.signal_id}:resolve",
        emission_type="m0.resolve.completed",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "entity_ref": entity_ref,
            "external_id": signal.payload.external_id,
        },
    )

    def updater(_: M0IngestionState) -> M0IngestionState:
        return M0IngestionState(
            ingested_count=state.ingested_count + 1,
            resolved_count=state.resolved_count + 1,
            last_entity_ref=entity_ref,
        )

    return [emission], updater


def _emit_step(signal: Signal[SocialIngestionEvent], state: M0IngestionState) -> StepResult:
    emission = Emission(
        emission_id=f"{signal.signal_id}:emit",
        emission_type="m0.event.ready",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "entity_ref": state.last_entity_ref,
            "ordinal": state.resolved_count,
        },
    )
    return [emission], None


def build_m0_ingestion_pipeline() -> Pipeline:
    """Create a deterministic ingest -> resolve -> emit pipeline for M0 flows."""

    return Pipeline(
        steps=[_ingest_step, _resolve_step, _emit_step],
        name="m0_ingest_resolve_emit",
    )


def make_m0_signal(
    *,
    signal_id: str,
    timestamp: datetime,
    source: str,
    platform: str,
    external_id: str,
    actor_ref: str,
    content_hash: str,
) -> Signal[SocialIngestionEvent]:
    """Factory for constructing stable-ID M0 social ingestion signals."""

    return Signal(
        signal_id=signal_id,
        timestamp=timestamp,
        source=source,
        payload=SocialIngestionEvent(
            platform=platform,
            external_id=external_id,
            actor_ref=actor_ref,
            content_hash=content_hash,
        ),
    )
