# Freqtrade Strategies

Bot-based trading strategies using the Freqtrade framework.

## Structure

```
freqtrade/
├── strategies/      # Strategy classes (IStrategy implementations)
├── configs/         # Bot configuration files (pairs, exchange, etc.)
├── hyperopts/       # Hyperopt custom loss functions & spaces
├── notebooks/       # Analysis notebooks for strategy development
└── plugins/         # Custom plugins (pairlist, protection, etc.)
```

## Setup

```bash
# Install Freqtrade
pip install freqtrade

# Or use Docker
docker compose up -d
```

## Quick Commands

```bash
# Backtesting
freqtrade backtesting --strategy MyStrategy -c freqtrade/configs/config.json

# Hyperopt
freqtrade hyperopt --strategy MyStrategy --hyperopt-loss SharpeHyperOptLoss -e 500

# Dry run
freqtrade trade --strategy MyStrategy -c freqtrade/configs/config.json --dry-run

# Download data
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT --timerange 20230101-
```

## Config Template

Place exchange-specific configs in `configs/`:
- `config.json` — main config (gitignored if contains keys)
- `config.example.json` — template without secrets
- `pairlist.json` — dynamic pairlist config
