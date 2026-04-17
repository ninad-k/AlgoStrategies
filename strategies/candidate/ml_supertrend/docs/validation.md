# Validation Notes

## Baseline

- Baseline backtest artifact: pending
- Cost model review: pending
- Out-of-sample window: pending

## Migration Notes

- Legacy root package content was moved into `strategies/candidate/ml_supertrend/`
- Core implementation now lives under `src/core/`
- Entry scripts now live under `src/`

## Next Steps

- update imports and entrypoints to reference the new package layout
- record a reproducible baseline backtest under `backtests/`
- document paper-trading results before promotion to production
