"""
Fear & Greed Index — Fetches the Crypto Fear & Greed Index.
"""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class FearGreedIndex:
    DEFAULT_URL = "https://api.alternative.me/fng/"

    def __init__(self, config: dict):
        self.url = config.get("url", self.DEFAULT_URL)

    def fetch(self) -> dict:
        """
        Fetch current Fear & Greed Index.

        Returns:
            dict with value (0-100), classification, timestamp
            0 = Extreme Fear, 100 = Extreme Greed
        """
        try:
            resp = requests.get(self.url, params={"limit": 1}, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("data"):
                entry = data["data"][0]
                value = int(entry["value"])
                classification = entry.get("value_classification", "")

                # Normalize to -1 to +1 scale
                normalized = (value - 50) / 50  # -1 (extreme fear) to +1 (extreme greed)

                return {
                    "value": value,
                    "normalized": round(normalized, 2),
                    "classification": classification,
                    "timestamp": datetime.fromtimestamp(int(entry["timestamp"])).isoformat(),
                }
        except Exception as e:
            logger.error(f"Fear & Greed fetch failed: {e}")

        return {"value": 50, "normalized": 0.0, "classification": "Neutral",
                "timestamp": datetime.now().isoformat()}
