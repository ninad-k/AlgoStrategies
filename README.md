# AlgoStrategies

A comprehensive algorithmic trading workspace for quant development, research, validation, and live execution.

## Repository Structure

```text
AlgoStrategies/
  strategies/        # Strategy lifecycle: incubator, candidate, production, retired
  platforms/         # Platform-specific adapters and framework assets (Pine, MT5, Freqtrade, options)
  shared/            # Reusable analytics, execution, risk, ML, ops, schemas, and utilities
  apps/              # Deployable dashboards, tools, mobile clients, and operations consoles
  backtesting/       # Shared backtesting engine, templates, reports, and exports
  research/          # Exploratory notebooks, papers, experiments, and imported community code
  data/              # Market data pipeline and datasets
  configs/           # Global broker, environment, universe, and risk configuration
  docs/              # Architecture, process, strategy, and setup documentation
  deploy/            # Deployment assets and service-specific infrastructure
  scripts/           # Utility automation and helper scripts
  tests/             # Cross-cutting unit, integration, and strategy validation tests
```

## Quick Start

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd AlgoStrategies
   ```

2. **Set up a Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies for the component you want to run**
   - Dashboards and tools keep their own dependency files under `apps/`
   - Shared Python modules and strategy packages may also have local `requirements.txt`

   For the Pine backtester specifically:
   ```bash
   cd apps/tools/backtester
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. **Configure credentials**
   ```bash
   cp configs/broker_config.example.yaml configs/broker_config.yaml
   cp .env.example .env
   ```

## Platforms And Apps

| Area | Location | Purpose |
|------|----------|---------|
| Strategy SDLC | `strategies/` | Strategy ownership, validation, and production readiness |
| Platform adapters | `platforms/` | Pine Script, MQL5, Freqtrade, options, and Python wrappers |
| Shared libraries | `shared/` | Reusable analytics, execution, risk, ML, and ops modules |
| Dashboards and tools | `apps/` | User-facing dashboards, scanners, tools, and mobile apps |
| Backtesting | `backtesting/` | Shared engine, configs, report templates, and exports |

## Documentation

- Strategy documentation template: `docs/templates/strategy_template.md`
- Options strategy template: `docs/templates/options_strategy_template.md`
- Freqtrade strategy template: `docs/templates/freqtrade_strategy_template.md`
- Strategy metadata template: `docs/templates/strategy.yaml.example`
- Repository structure guide: `docs/architecture/repo_structure.md`
- Strategy SDLC process: `docs/processes/strategy_sdlc.md`
- Promotion checklist: `docs/processes/promotion_checklist.md`

## Conventions

- Every production-bound strategy should have a `strategy.yaml`
- Backtest reports live under `backtesting/reports/`
- Backtest summaries live under `backtesting/results/<platform>/`
- Exports live under `backtesting/exports/`
- Secrets are never committed; use `.example` files instead
- Research notebooks should use a numbered prefix for ordering

## Contributing

1. Create a feature branch from `main`
2. Add or update strategy documentation in `docs/` or the strategy package
3. Include reproducible backtest outputs for strategy changes
4. Run relevant tests before merging
