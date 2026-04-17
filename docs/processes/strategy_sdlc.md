# Strategy SDLC

## Lifecycle States

### Incubator
Use for ideas and early hypotheses.
Required:
- strategy thesis
- target market/instrument
- entry and exit concept
- invalidation conditions
- owner

### Candidate
Use for implemented strategies with reproducible backtests.
Required:
- executable source code
- strategy metadata
- baseline backtest
- transaction cost and slippage assumptions
- unit or rule-validation tests

### Validation
Use for strategies under deeper review before production.
Required:
- out-of-sample tests
- walk-forward analysis
- parameter sensitivity analysis
- paper-trading or shadow-trading notes
- risk review

### Production
Use for live or live-ready strategies.
Required:
- approved validation pack
- deployment config
- monitoring and alerting
- runbook
- rollback procedure

### Retired
Use for strategies no longer maintained or deployed.
Required:
- retirement date
- retirement reason
- summary of lessons learned

## Promotion Gates

- `incubator -> candidate`: documented hypothesis and initial implementation exist
- `candidate -> validation`: baseline backtest is reproducible and documented
- `validation -> production`: validation evidence, risk review, and runbook are complete
- `production -> retired`: strategy is disabled and postmortem is captured