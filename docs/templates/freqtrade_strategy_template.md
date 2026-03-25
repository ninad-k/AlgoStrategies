# Freqtrade Strategy: [Name]

## Overview
- **Strategy Class**: `[ClassName]`
- **Timeframe**: [5m / 15m / 1h]
- **Pairs**: [BTC/USDT, ETH/USDT, etc.]
- **Exchange**: [Binance / Bybit / etc.]
- **Version**: v1.0
- **Status**: [Research / Backtested / Dry Run / Live]

## Strategy Logic
Describe the core trading logic and market condition this targets.

## Parameters
| Parameter | Default | Optimized | Description |
|-----------|---------|-----------|-------------|
| buy_rsi | | | RSI threshold for buy |
| sell_rsi | | | RSI threshold for sell |
| | | | |

## Entry (populate_entry_trend)
1. Condition 1
2. Condition 2
3. Tag: `"entry_reason"`

## Exit (populate_exit_trend)
1. Condition 1
2. Tag: `"exit_reason"`

## Custom Stoploss / ROI
```
minimal_roi = {
    "0": 0.10,
    "30": 0.05,
    "60": 0.02,
}
stoploss = -0.05
trailing_stop = True
trailing_stop_positive = 0.01
```

## Hyperopt Results
| Parameter | Space | Best Value |
|-----------|-------|------------|
| | | |

## Backtest Command
```bash
freqtrade backtesting --strategy [ClassName] \
  --timerange 20240101-20241231 \
  --timeframe 1h \
  -c freqtrade/configs/config.json
```

## Backtest Results
| Metric | Value |
|--------|-------|
| Period | |
| Total Trades | |
| Win Rate | |
| Profit Factor | |
| Sharpe Ratio | |
| Max Drawdown | |
| Avg Duration | |

## Dependencies
- Indicators: [ta-lib, pandas-ta, etc.]
- Data provider: [exchange API]
- Custom modules: [if any]

## Changelog
| Date | Version | Change |
|------|---------|--------|
|      | v1.0    | Initial version |
