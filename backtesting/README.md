# Backtesting

## Structure

```
backtesting/
├── engine/              # Custom backtesting engine code
├── configs/             # Backtest parameter configs (YAML)
├── templates/           # Report templates
├── reports/             # Generated HTML/PDF reports (gitignored)
├── results/             # Backtest result summaries per platform
│   ├── pinescript/      # TradingView strategy tester exports
│   ├── mql5/            # MT5 strategy tester results
│   ├── freqtrade/       # Freqtrade backtest JSON results
│   ├── options/         # Options strategy backtest results
│   └── python/          # Custom Python backtester results
└── exports/             # Exported CSV/XLSX data (gitignored)
    ├── trades/          # Individual trade logs (entry, exit, PnL, duration)
    ├── equity_curves/   # Equity curve time series
    ├── metrics/         # Summary metrics (Sharpe, drawdown, win rate, etc.)
    └── raw/             # Raw exported data from platforms
```

## Naming Convention

### Results
```
results/<platform>/<STRATEGY_NAME>_<SYMBOL>_<TIMEFRAME>_<DATERANGE>.<ext>
```
Example: `results/pinescript/MeanReversion_NIFTY_15m_20240101-20241231.json`

### Exports
```
exports/<type>/<STRATEGY_NAME>_<SYMBOL>_<DATERANGE>.<ext>
```
Examples:
- `exports/trades/IronCondor_BANKNIFTY_20240101-20241231.csv`
- `exports/equity_curves/TrendFollower_EURUSD_20230601-20241231.csv`
- `exports/metrics/MomentumBot_BTCUSDT_20240101-20241231.csv`

## Export CSV Formats

### trades/ columns
`trade_id, strategy, symbol, direction, entry_time, exit_time, entry_price, exit_price, quantity, pnl, pnl_pct, fees, duration, exit_reason, tags`

### equity_curves/ columns
`timestamp, equity, drawdown, drawdown_pct, daily_return`

### metrics/ columns
`metric, value` (key-value pairs: total_trades, win_rate, profit_factor, sharpe_ratio, max_drawdown, cagr, avg_trade_duration, etc.)

## Notes
- Large CSV/XLSX files are gitignored — only `.gitkeep` placeholders are committed
- Store small summary JSONs in `results/` for version tracking
- Use `backtesting/configs/` to define reproducible backtest parameters
