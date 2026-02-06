# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial open-source release.
- Core types: `Signal`, `Emission`, `State`.
- `Pipeline` and `Engine` for processing signals.
- Transforms: `accumulate`, `update_state`, `emit`, `emit_if`, `branch`, `merge`, `window`, and others.
- Protocols: `GameProtocol`, `SignalSource`, `EmissionSink`, and related.
- Example: `PodcastGame` in `metaspn_engine.podcast_game`.
- Deterministic emission options in emission-producing transforms via `emission_id_factory` and `timestamp_factory`.
- Contract-focused tests for signal identity/serialization, `caused_by` traceability, and emission ordering.
- Integration guardrails documentation for `metaspn-schemas` + `metaspn-store` + `metaspn-ops` boundaries.
- M0 ingestion reference module (`metaspn_engine.m0_ingestion`) for ingest -> resolve -> emit orchestration.
- M0 deterministic traceability tests for `caused_by` linkage and emission ordering.
- README guidance on engine-direct usage vs worker-level orchestration.
- M1 routing reference module (`metaspn_engine.m1_routing`) for profile -> score -> route composition.
- M1 deterministic traceability tests for emission ordering and `caused_by` propagation.
- README guidance for M1 engine composition vs worker orchestration boundaries.
- M2 recommendation reference module (`metaspn_engine.m2_recommendations`) for ranking -> draft composition.
- Deterministic M2 tests for ranking order under equal/near-equal scores and `caused_by` propagation.
- README guidance for mapping M2 engine composition to `metaspn-ops` and `metaspn-store` boundaries.
- M3 learning reference module (`metaspn_engine.m3_learning`) for attempt -> outcome -> failure -> calibration flow.
- Deterministic M3 tests for full stage ordering and `caused_by` continuity across learning stages.
- README guidance for M3 engine composition vs worker-stage orchestration boundaries.
- Demo traceability mapping helper (`metaspn_engine.demo_support`) covering M0-M3 stage suffix expectations.
- Demo alignment tests for M2 shortlist and M3 learning report deterministic traces.
- README guidance for demo-stage chaining and trace/debug semantics across ops/store boundaries.

## [0.1.0] - 2025-01-29

### Added

- First release.

[Unreleased]: https://github.com/metaspn/metaspn-engine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/metaspn/metaspn-engine/releases/tag/v0.1.0
