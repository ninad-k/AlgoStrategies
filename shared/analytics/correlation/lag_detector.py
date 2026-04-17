"""
Lag Detector — Cross-correlation with configurable time lags.
Finds which asset leads/follows another.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LagDetector:
    def __init__(self, config: dict):
        corr_cfg = config.get("correlation", {})
        self.max_lag = corr_cfg.get("lag_max_minutes", 30)

    def detect_lag(self, returns_a: pd.Series, returns_b: pd.Series,
                   symbol_a: str = "A", symbol_b: str = "B") -> dict:
        """
        Find the optimal lag between two return series using cross-correlation.

        Args:
            returns_a, returns_b: Price return series
            symbol_a, symbol_b: Symbol names for labeling

        Returns:
            dict with:
                best_lag: int (positive = A leads B, negative = B leads A)
                best_correlation: float
                lag_profile: list of {lag, correlation}
                leader: str (which symbol leads)
        """
        aligned = pd.concat(
            [returns_a.rename("a"), returns_b.rename("b")], axis=1
        ).dropna()

        if len(aligned) < self.max_lag * 2:
            return {"best_lag": 0, "best_correlation": 0, "lag_profile": [],
                    "leader": "none"}

        a_vals = aligned["a"].values
        b_vals = aligned["b"].values

        lag_profile = []
        best_lag = 0
        best_corr = 0

        for lag in range(-self.max_lag, self.max_lag + 1):
            if lag > 0:
                corr = np.corrcoef(a_vals[:-lag], b_vals[lag:])[0, 1]
            elif lag < 0:
                corr = np.corrcoef(a_vals[-lag:], b_vals[:lag])[0, 1]
            else:
                corr = np.corrcoef(a_vals, b_vals)[0, 1]

            if not np.isnan(corr):
                lag_profile.append({"lag": lag, "correlation": round(float(corr), 4)})
                if abs(corr) > abs(best_corr):
                    best_corr = float(corr)
                    best_lag = lag

        # Determine leader
        if best_lag > 0:
            leader = symbol_a  # A leads B by `best_lag` bars
        elif best_lag < 0:
            leader = symbol_b  # B leads A
        else:
            leader = "simultaneous"

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "best_lag": best_lag,
            "best_correlation": round(best_corr, 4),
            "lag_profile": lag_profile,
            "leader": leader,
            "interpretation": (
                f"{leader} leads by {abs(best_lag)} bars (corr={best_corr:.3f})"
                if leader not in ("none", "simultaneous")
                else "No clear lead-lag relationship"
            ),
        }
