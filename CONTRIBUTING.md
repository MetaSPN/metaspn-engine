# Contributing to MetaSPN Engine

Thanks for your interest in contributing. This document covers how to set up the project, run checks, and submit changes.

## Development setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/metaspn/metaspn-engine.git
   cd metaspn-engine
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install in editable mode with dev dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

## Running tests and checks

- **Tests:** `pytest tests/ -v`
- **Lint:** `ruff check .`
- **Type check:** `mypy metaspn_engine/`

CI runs all of the above on push/PR to `main` (or `master`).

## Submitting changes

1. Open an issue or pick an existing one to discuss the change.
2. Branch from `main`, make your changes, and add/update tests as needed.
3. Ensure `pytest`, `ruff check .`, and `mypy metaspn_engine/` all pass.
4. Open a pull request with a clear description and reference to any issue.
5. Keep the PR focused; avoid unrelated edits.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines and [SECURITY.md](SECURITY.md) for how to report security issues.
