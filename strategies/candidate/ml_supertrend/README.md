# ML Supertrend

Candidate-stage strategy package for the ML-enhanced Supertrend workflow.

## Layout

- `strategy.yaml`: lifecycle metadata and deployment intent
- `config/`: strategy configuration and parameters
- `src/`: executable code for training, backtesting, and bot runtime
- `tests/`: strategy-specific validation tests
- `docs/`: validation notes and supporting documentation
- `backtests/`: reproducible baseline outputs
- `artifacts/`: generated strategy artifacts that are intentionally versioned
- `runbooks/`: paper-trading and live-ops procedures

## Current Status

This package was migrated from the legacy `ml-supertrend/` root folder into the SDLC-oriented `strategies/candidate/` tree. Import paths may still need follow-up cleanup before running all entrypoints unchanged.
