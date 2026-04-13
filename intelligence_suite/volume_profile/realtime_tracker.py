"""
Real-time Volume Profile Tracker — Updates profile as new candles arrive.
"""

import logging
from datetime import datetime

import pandas as pd

from .tpo_builder import TPOBuilder
from .profile_calculator import VolumeProfileCalculator

logger = logging.getLogger(__name__)


class RealtimeVolumeTracker:
    def __init__(self, config: dict):
        self.tpo_builder = TPOBuilder(config)
        self.calculator = VolumeProfileCalculator(config)
        self.profiles = {}  # symbol -> latest profile result
        self.tick_sizes = {}  # symbol -> detected tick size

    def update(self, symbol: str, df: pd.DataFrame) -> dict:
        """
        Update volume profile for a symbol with latest OHLCV data.

        Returns the full profile result with POC, VAH, VAL, HVN, LVN.
        """
        tick_size = self.tick_sizes.get(symbol)
        tpo_data = self.tpo_builder.build(df, tick_size)

        if not tpo_data.get("levels"):
            return self.profiles.get(symbol, {})

        # Cache tick size for consistency
        if "tick_size" in tpo_data:
            self.tick_sizes[symbol] = tpo_data["tick_size"]

        profile = self.calculator.calculate(tpo_data)
        profile["symbol"] = symbol
        profile["timestamp"] = datetime.now().isoformat()
        profile["tpo_data"] = {
            "periods": tpo_data["periods"],
            "total_tpos": tpo_data["total_tpos"],
        }

        self.profiles[symbol] = profile
        return profile

    def get_profile(self, symbol: str) -> dict:
        """Get the latest cached profile for a symbol."""
        return self.profiles.get(symbol, {})

    def get_key_levels(self, symbol: str) -> dict:
        """Get just the key levels (POC, VAH, VAL) for quick access."""
        profile = self.profiles.get(symbol, {})
        return {
            "poc": profile.get("poc", 0),
            "vah": profile.get("vah", 0),
            "val": profile.get("val", 0),
            "hvn": profile.get("hvn", []),
            "lvn": profile.get("lvn", []),
        }
