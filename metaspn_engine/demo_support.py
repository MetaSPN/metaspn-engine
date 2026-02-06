"""Helpers for aligning demo orchestration with engine reference traces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoStageSpec:
    """Reference metadata for a demo stage backed by an engine pipeline."""

    stage_key: str
    pipeline_name: str
    module_name: str
    emission_suffixes: tuple[str, ...]


def demo_stage_specs() -> dict[str, DemoStageSpec]:
    """Return demo stage mapping to engine reference pipelines."""

    return {
        "m0_ingest": DemoStageSpec(
            stage_key="m0_ingest",
            pipeline_name="m0_ingest_resolve_emit",
            module_name="metaspn_engine.m0_ingestion",
            emission_suffixes=("ingest", "resolve", "emit"),
        ),
        "m1_route": DemoStageSpec(
            stage_key="m1_route",
            pipeline_name="m1_profile_score_route",
            module_name="metaspn_engine.m1_routing",
            emission_suffixes=("profile", "score", "route"),
        ),
        "m2_shortlist": DemoStageSpec(
            stage_key="m2_shortlist",
            pipeline_name="m2_rank_and_draft",
            module_name="metaspn_engine.m2_recommendations",
            emission_suffixes=("recommendation", "draft"),
        ),
        "m3_learning": DemoStageSpec(
            stage_key="m3_learning",
            pipeline_name="m3_attempt_outcome_failure_calibration",
            module_name="metaspn_engine.m3_learning",
            emission_suffixes=("attempt", "outcome", "failure", "calibration"),
        ),
    }


def expected_emission_ids(signal_id: str, stage_key: str) -> list[str]:
    """Build deterministic emission IDs for a given demo stage and signal ID."""

    spec = demo_stage_specs()[stage_key]
    return [f"{signal_id}:{suffix}" for suffix in spec.emission_suffixes]
