"""
Correlation Tracker — Rolling Pearson/Spearman correlation between asset pairs.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CorrelationTracker:
    def __init__(self, config: dict):
        corr_cfg = config.get("correlation", {})
        self.rolling_window = corr_cfg.get("rolling_window", 60)
        self.pairs = corr_cfg.get("pairs", [])
        self.history = {}  # "BTCUSD_ETHUSD" -> list of {timestamp, pearson, spearman}

    def update(self, returns_dict: dict[str, pd.Series]) -> dict:
        """
        Compute rolling correlations between all configured pairs.

        Args:
            returns_dict: {symbol: pd.Series of returns}

        Returns:
            dict of pair -> {pearson, spearman, timestamp}
        """
        results = {}

        for pair in self.pairs:
            if len(pair) != 2:
                continue
            sym_a, sym_b = pair
            if sym_a not in returns_dict or sym_b not in returns_dict:
                continue

            ret_a = returns_dict[sym_a].tail(self.rolling_window)
            ret_b = returns_dict[sym_b].tail(self.rolling_window)

            # Align series
            aligned = pd.concat([ret_a, ret_b], axis=1, keys=[sym_a, sym_b]).dropna()
            if len(aligned) < 10:
                continue

            pearson = float(aligned[sym_a].corr(aligned[sym_b]))
            spearman = float(aligned[sym_a].corr(aligned[sym_b], method="spearman"))

            pair_key = f"{sym_a}_{sym_b}"
            entry = {
                "pair": pair_key,
                "pearson": round(pearson, 4),
                "spearman": round(spearman, 4),
                "n_obs": len(aligned),
                "timestamp": datetime.now().isoformat(),
            }

            if pair_key not in self.history:
                self.history[pair_key] = []
            self.history[pair_key].append(entry)
            if len(self.history[pair_key]) > 500:
                self.history[pair_key] = self.history[pair_key][-250:]

            results[pair_key] = entry

        return results

    def get_correlation_matrix(self, returns_dict: dict[str, pd.Series]) -> dict:
        """Compute full correlation matrix across all symbols."""
        symbols = list(returns_dict.keys())
        if len(symbols) < 2:
            return {}

        df = pd.DataFrame(returns_dict).dropna()
        if len(df) < 10:
            return {}

        corr_matrix = df.corr().round(4)
        return corr_matrix.to_dict()

    def get_history(self, pair_key: str, limit: int = 50) -> list:
        return self.history.get(pair_key, [])[-limit:]
