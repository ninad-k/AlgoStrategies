# Repository Structure

## Principles

- `strategies/` owns strategy lifecycle, ownership, validation, and deployment readiness.
- `platforms/` owns platform-specific adapters and reusable framework code.
- `shared/` owns reusable analytics, execution, risk, data, and ML components.
- `apps/` owns deployable dashboards, tools, mobile clients, and operational consoles.
- `research/` is exploratory only and is not considered production-ready.
- `backtesting/` owns shared backtest infrastructure and templates.

## Top-Level Layout

```text
AlgoStrategies/
  strategies/
    incubator/
    candidate/
    production/
    retired/
  platforms/
    pinescript/
    mql5/
    freqtrade/
    python/
    options/
  shared/
    analytics/
    data/
    execution/
    risk/
    ml/
    ops/
    utils/
  apps/
    dashboards/
    tools/
    mobile/
    operations/
  backtesting/
  research/
  data/
  configs/
  docs/
  deploy/
  scripts/
  tests/
```

## Strategy Ownership

Each strategy must live in exactly one lifecycle state under `strategies/`.
Each strategy must define:
- owner
- status
- supported platforms
- market and timeframe
- risk limits
- validation artifacts
- deployment target

## Rules

- Do not create new product folders at repo root.
- Do not store generated runtime artifacts in source-controlled app or strategy folders.
- Do not place strategy-specific business logic inside `platforms/` unless it is a thin adapter.
- Do not promote research code directly to production without creating a formal strategy package.