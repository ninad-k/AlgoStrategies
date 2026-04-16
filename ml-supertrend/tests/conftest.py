import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Synthetic OHLCV with enough bars for ATR/rolling warmup (~300)."""
    n = 320
    rng = np.random.default_rng(42)
    t = pd.date_range("2024-01-01", periods=n, freq="30min", tz="UTC")
    walk = np.cumsum(rng.normal(0, 0.0003, n)) + 1.10
    close = walk.astype(np.float64)
    noise = rng.uniform(0.0001, 0.0008, n)
    high = close + noise
    low = close - noise
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    vol = rng.integers(50, 500, n).astype(np.float64)
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": vol,
            "spread": np.zeros(n, dtype=np.int32),
            "real_volume": vol,
        },
        index=t,
    )
    df.index.name = "time"
    return df
