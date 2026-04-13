"""
Pair Finder — Cointegration testing and mean-reversion pair suggestions.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PairFinder:
    def __init__(self, config: dict):
        self.config = config

    def test_cointegration(self, prices_a: pd.Series, prices_b: pd.Series,
                           symbol_a: str = "A", symbol_b: str = "B") -> dict:
        """
        Engle-Granger cointegration test between two price series.

        Returns:
            dict with:
                is_cointegrated: bool
                p_value: float
                test_stat: float
                hedge_ratio: float
                half_life: float (mean reversion speed in bars)
                spread_zscore: float (current z-score of spread)
        """
        try:
            from statsmodels.tsa.stattools import coint, adfuller
        except ImportError:
            logger.warning("statsmodels not installed")
            return {"is_cointegrated": False, "error": "statsmodels not installed"}

        aligned = pd.concat(
            [prices_a.rename("a"), prices_b.rename("b")], axis=1
        ).dropna()

        if len(aligned) < 60:
            return {"is_cointegrated": False, "error": "insufficient data"}

        a_vals = aligned["a"].values
        b_vals = aligned["b"].values

        # Cointegration test
        score, p_value, _ = coint(a_vals, b_vals)

        # Hedge ratio via OLS
        hedge_ratio = float(np.polyfit(b_vals, a_vals, 1)[0])

        # Compute spread
        spread = a_vals - hedge_ratio * b_vals
        spread_mean = spread.mean()
        spread_std = spread.std()
        spread_zscore = float((spread[-1] - spread_mean) / spread_std) if spread_std > 0 else 0

        # Half-life of mean reversion
        half_life = self._calc_half_life(spread)

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "is_cointegrated": p_value < 0.05,
            "p_value": round(float(p_value), 4),
            "test_stat": round(float(score), 4),
            "hedge_ratio": round(hedge_ratio, 4),
            "half_life": round(half_life, 1),
            "spread_zscore": round(spread_zscore, 3),
            "spread_mean": round(float(spread_mean), 4),
            "spread_std": round(float(spread_std), 4),
            "interpretation": (
                f"Cointegrated (p={p_value:.3f}). "
                f"Half-life={half_life:.0f} bars. "
                f"Current z-score={spread_zscore:.2f}"
                if p_value < 0.05
                else f"Not cointegrated (p={p_value:.3f})"
            ),
        }

    def _calc_half_life(self, spread: np.ndarray) -> float:
        """Calculate half-life of mean reversion using Ornstein-Uhlenbeck model."""
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)

        if len(spread_lag) < 2:
            return float("inf")

        # OLS: delta_spread = beta * spread_lag + epsilon
        beta = np.polyfit(spread_lag, spread_diff, 1)[0]

        if beta >= 0:
            return float("inf")  # Not mean reverting

        half_life = -np.log(2) / beta
        return max(1, min(500, float(half_life)))

    def find_best_pairs(self, prices_dict: dict[str, pd.Series],
                        max_pairs: int = 5) -> list[dict]:
        """
        Test all combinations and return the best cointegrated pairs.
        """
        symbols = list(prices_dict.keys())
        results = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                result = self.test_cointegration(
                    prices_dict[symbols[i]], prices_dict[symbols[j]],
                    symbols[i], symbols[j],
                )
                if result.get("is_cointegrated"):
                    results.append(result)

        # Sort by p-value (lower = stronger cointegration)
        results.sort(key=lambda x: x.get("p_value", 1))
        return results[:max_pairs]
