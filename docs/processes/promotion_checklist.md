# Promotion Checklist

## Candidate to Validation

- `strategy.yaml` exists and is complete
- source code is runnable
- baseline backtest is reproducible
- assumptions for fees, spread, and slippage are documented
- tests cover critical rule logic
- owner is assigned

## Validation to Production

- out-of-sample results recorded
- walk-forward results recorded
- parameter sensitivity reviewed
- failure modes documented
- max risk per trade and daily loss limits defined
- deployment target configured
- monitoring and alerts configured
- runbook exists
- rollback plan exists

## Production to Retired

- live deployment disabled
- retirement reason documented
- open operational tasks closed
- artifacts archived
- lessons learned captured