# AlgoStrategies

A comprehensive algorithmic trading workspace for quant development, research, and live execution.

## Repository Structure

```
├── pinescript/          # TradingView Pine Scripts (strategies, indicators, libraries, alerts)
├── mql5/                # MetaTrader 5 (Expert Advisors, indicators, scripts, libraries)
├── freqtrade/           # Freqtrade bot strategies, hyperopts, and configs
├── options/             # Options strategies (Indian market focus: NSE/BSE)
├── models/              # AI/ML models (training, inference, feature engineering)
├── backtesting/         # Backtesting engine, reports, results, and CSV exports
├── data/                # Market data pipeline (raw → processed → alternative)
├── research/            # Quant research notebooks, alpha signals, statistical tests
├── risk_management/     # Position sizing, portfolio optimization, drawdown analysis
├── execution/           # Live execution (broker APIs, OMS, webhooks, schedulers)
├── monitoring/          # Dashboards, trade logging, notifications (Telegram/Discord)
├── tools/               # Utilities (screeners, calculators, converters, CLI)
├── docs/                # Documentation for all components
├── configs/             # Global configs (symbols, timeframes, environments)
└── tests/               # Unit, integration, and strategy validation tests
```

## Quick Start

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd AlgoStrategies
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```

   PyCharm: prefer a repo-local interpreter for this project. Do not use an unrelated
   `PyCharmMiscProject\.venv` or another scratch-project environment.

   For the Pine backtester specifically:
   ```bash
   cd tools/backtester
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   Then point the PyCharm project interpreter to `tools/backtester/.venv/Scripts/python.exe`
   before running the shared `Backtester` configuration.

3. **Configure broker credentials**
   ```bash
   cp configs/broker_config.example.yaml configs/broker_config.yaml
   # Edit with your API keys
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Fill in your secrets
   ```

## Platforms & Tools

| Platform     | Location         | Purpose                           |
|-------------|-----------------|-----------------------------------|
| TradingView | `pinescript/`    | Chart-based strategies & alerts   |
| MetaTrader 5| `mql5/`          | Automated EA trading              |
| Freqtrade   | `freqtrade/`     | Crypto & multi-exchange bot       |
| Options     | `options/`       | NSE/BSE options strategies        |
| Python ML   | `models/`        | ML-driven signals & predictions   |

## Documentation

- Strategy documentation template: `docs/templates/strategy_template.md`
- Options strategy template: `docs/templates/options_strategy_template.md`
- Freqtrade strategy template: `docs/templates/freqtrade_strategy_template.md`
- Setup guides: `docs/setup/`

## Conventions

- **Strategy naming**: `<TYPE>_<NAME>_<VERSION>` (e.g., `PINE_MeanReversion_v1.pine`)
- **Backtest reports**: stored in `backtesting/reports/` with date prefix
- **Backtest results**: per-platform results in `backtesting/results/<platform>/`
- **Backtest exports**: CSV/XLSX trade logs and equity curves in `backtesting/exports/`
- **Config files**: YAML format, secrets never committed (use `.example` templates)
- **Research notebooks**: numbered prefix for ordering (e.g., `01_data_exploration.ipynb`)

## Contributing

1. Create a feature branch from `main`
2. Add strategy documentation using templates in `docs/templates/`
3. Include backtest results for any new strategy
4. Run tests before merging: `pytest tests/`
