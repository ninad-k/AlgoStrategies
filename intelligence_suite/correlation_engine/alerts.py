"""
Correlation Alerts — Notify when correlations break or regimes shift.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CorrelationAlerts:
    def __init__(self, config: dict):
        self.threshold_drop = 0.3  # Alert if correlation drops by this much
        self.baseline = {}  # pair -> baseline correlation
        self.alerts = []

    def set_baseline(self, pair: str, correlation: float):
        """Set the baseline correlation for a pair."""
        self.baseline[pair] = correlation

    def check(self, pair: str, current_correlation: float) -> dict | None:
        """
        Check if correlation has significantly changed from baseline.

        Returns alert dict if triggered, None otherwise.
        """
        if pair not in self.baseline:
            self.baseline[pair] = current_correlation
            return None

        base = self.baseline[pair]
        change = abs(current_correlation - base)

        if change >= self.threshold_drop:
            alert = {
                "type": "CORRELATION_BREAK",
                "pair": pair,
                "baseline": round(base, 3),
                "current": round(current_correlation, 3),
                "change": round(change, 3),
                "direction": "weakened" if abs(current_correlation) < abs(base) else "strengthened",
                "timestamp": datetime.now().isoformat(),
                "message": (
                    f"{pair} correlation changed from {base:.3f} to {current_correlation:.3f} "
                    f"(delta={change:.3f})"
                ),
            }
            self.alerts.append(alert)
            if len(self.alerts) > 200:
                self.alerts = self.alerts[-100:]

            # Update baseline
            self.baseline[pair] = current_correlation
            logger.warning(alert["message"])
            return alert

        return None

    def get_recent_alerts(self, limit: int = 20) -> list:
        return self.alerts[-limit:]
