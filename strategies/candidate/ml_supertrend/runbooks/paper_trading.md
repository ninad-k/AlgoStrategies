# Paper Trading Runbook

## Preconditions

- local Python environment created from this package
- broker and environment configuration reviewed
- baseline backtest captured and approved for paper deployment

## Procedure

1. Install dependencies from `requirements.txt`.
2. Review `strategy.yaml` and `config/strategy.json`.
3. Launch the bot in paper mode using the package entrypoint.
4. Monitor decisions, fills, and risk events.
5. Record anomalies, downtime, and execution mismatches.

## Exit Criteria

- paper-trading window completed
- no critical execution or risk defects remain
- validation notes updated in `docs/validation.md`
