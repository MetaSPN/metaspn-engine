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

## [0.1.0] - 2025-01-29

### Added

- First release.

[Unreleased]: https://github.com/metaspn/metaspn-engine/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/metaspn/metaspn-engine/releases/tag/v0.1.0
