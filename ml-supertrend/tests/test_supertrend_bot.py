"""SuperTrendBot math path (no broker / no MT5 initialize)."""

import MetaTrader5 as mt5
import numpy as np

from core.data_fetcher import add_base_indicators
from core.supertrend_bot import Config, SuperTrendBot


def test_calculate_supertrends_and_clustering(sample_ohlcv):
    # Warm up indicators so vol_adj_perf means used in clustering are finite
    df = add_base_indicators(sample_ohlcv).iloc[200:].copy()
    cfg = Config(
        symbol="EURUSD",
        timeframe=mt5.TIMEFRAME_M30,
        min_factor=1.0,
        max_factor=3.0,
        factor_step=0.5,
        cluster_choice="Average",
    )
    bot = SuperTrendBot(cfg)
    supertrends = bot.calculate_supertrends(df)
    assert len(supertrends) == 5
    for _f, st in supertrends.items():
        assert "trend" in st.columns and "vol_adj_perf" in st.columns

    optimal, score = bot.perform_clustering(supertrends)
    assert isinstance(optimal, (float, np.floating))
    assert isinstance(score, (float, np.floating))


def test_check_volume_condition(sample_ohlcv):
    df = add_base_indicators(sample_ohlcv)
    cfg = Config(
        symbol="EURUSD",
        timeframe=mt5.TIMEFRAME_M30,
        volume_multiplier=0.5,
    )
    bot = SuperTrendBot(cfg)
    assert bot.check_volume_condition(df) in (True, False)
