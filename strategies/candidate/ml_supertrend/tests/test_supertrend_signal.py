"""evaluate_signal uses the same path as live bot (no MT5 orders)."""

import MetaTrader5 as mt5

from core.supertrend_bot import Config, SuperTrendBot


def test_evaluate_signal_returns_direction(sample_ohlcv):
    cfg = Config(
        symbol="EURUSD",
        timeframe=mt5.TIMEFRAME_M30,
        min_factor=1.0,
        max_factor=3.0,
        factor_step=0.5,
        cluster_choice="Average",
        volume_multiplier=0.5,
    )
    bot = SuperTrendBot(cfg)
    df = bot.prepare_dataframe(sample_ohlcv.copy())
    out = bot.evaluate_signal(df)
    assert "direction" in out
    assert out["direction"] in (-1, 0, 1)
