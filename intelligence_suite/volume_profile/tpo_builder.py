"""
TPO Builder — Constructs Time Price Opportunity profiles from OHLCV data.

Each TPO period (default 30 min) is represented by a letter (A, B, C...).
The TPO chart shows how long price spent at each level.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TPOBuilder:
    def __init__(self, config: dict):
        vp_cfg = config.get("volume_profile", {})
        self.tpo_period_minutes = vp_cfg.get("tpo_period_minutes", 30)
        self.tick_size = None  # Auto-detected from data

    def build(self, df: pd.DataFrame, tick_size: float = None) -> dict:
        """
        Build TPO profile from OHLCV DataFrame.

        Args:
            df: OHLCV DataFrame with datetime index
            tick_size: Price increment for binning. Auto-detected if None.

        Returns:
            dict with:
                levels: list of {price, tpo_count, volume, letters}
                periods: list of period labels (A, B, C...)
                total_tpos: int
        """
        if df is None or len(df) < 10:
            return {"levels": [], "periods": [], "total_tpos": 0}

        # Auto-detect tick size from price range
        if tick_size is None:
            price_range = float(df["high"].max() - df["low"].min())
            # Aim for ~50-100 price levels
            tick_size = price_range / 80
            if tick_size <= 0:
                tick_size = 0.01

        self.tick_size = tick_size

        # Determine price bins
        price_min = float(df["low"].min())
        price_max = float(df["high"].max())
        bins = np.arange(price_min, price_max + tick_size, tick_size)
        bin_centers = (bins[:-1] + bins[1:]) / 2

        # Initialize TPO grid
        tpo_grid = {round(float(p), 6): {"tpo_count": 0, "volume": 0, "letters": []}
                     for p in bin_centers}

        # Group candles into TPO periods
        if hasattr(df.index, 'hour'):
            # Time-based grouping
            period_minutes = self.tpo_period_minutes
            df = df.copy()
            df["period"] = (df.index.hour * 60 + df.index.minute) // period_minutes
        else:
            # Index-based grouping
            df = df.copy()
            bars_per_period = max(1, self.tpo_period_minutes)  # Assume 1-min bars
            df["period"] = np.arange(len(df)) // bars_per_period

        period_labels = []
        for period_idx, (period, group) in enumerate(df.groupby("period")):
            letter = chr(65 + (period_idx % 26))  # A-Z
            period_labels.append(letter)

            for _, bar in group.iterrows():
                bar_low = float(bar["low"])
                bar_high = float(bar["high"])
                bar_volume = float(bar["volume"])

                # Find which bins this bar touches
                touched_bins = bin_centers[
                    (bin_centers >= bar_low - tick_size / 2) &
                    (bin_centers <= bar_high + tick_size / 2)
                ]

                vol_per_bin = bar_volume / max(len(touched_bins), 1)

                for price in touched_bins:
                    key = round(float(price), 6)
                    if key in tpo_grid:
                        tpo_grid[key]["tpo_count"] += 1
                        tpo_grid[key]["volume"] += vol_per_bin
                        if letter not in tpo_grid[key]["letters"]:
                            tpo_grid[key]["letters"].append(letter)

        # Convert to sorted list
        levels = []
        for price, data in sorted(tpo_grid.items()):
            if data["tpo_count"] > 0:
                levels.append({
                    "price": round(price, 4),
                    "tpo_count": data["tpo_count"],
                    "volume": round(data["volume"], 2),
                    "letters": "".join(data["letters"]),
                })

        total_tpos = sum(l["tpo_count"] for l in levels)

        return {
            "levels": levels,
            "periods": period_labels,
            "total_tpos": total_tpos,
            "tick_size": round(tick_size, 6),
        }
