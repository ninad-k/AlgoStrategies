# Backtest entry points (historical simulation via MT5 rates).
# Prefer ``run_backtest.py`` or ``core.backtest_mt5`` for new code.

from core.backtest_mt5 import (
    BacktestStats,
    TIMEFRAME_MAP,
    ensure_mt5,
    fetch_rates_range,
    run_cluster_backtest,
    run_ml_backtest,
    timeframe_from_string,
)

__all__ = [
    "BacktestStats",
    "TIMEFRAME_MAP",
    "ensure_mt5",
    "fetch_rates_range",
    "run_cluster_backtest",
    "run_ml_backtest",
    "timeframe_from_string",
]
