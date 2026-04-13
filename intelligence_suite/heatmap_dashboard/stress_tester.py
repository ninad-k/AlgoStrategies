"""
ReySentinel — Stress Tester
=====================================
Runs predefined stress-test scenarios against the portfolio.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class StressTester:
    """Applies predefined market shock scenarios to a portfolio."""

    SCENARIOS: dict[str, float] = {
        "flash_crash": -0.10,
        "rate_shock": -0.05,
        "crypto_winter": -0.30,
        "black_swan": -0.20,
        "liquidity_crisis": -0.15,
        "correlation_spike": -0.12,
    }

    SCENARIO_DESCRIPTIONS: dict[str, str] = {
        "flash_crash": "Sudden 10% market-wide decline in minutes",
        "rate_shock": "Unexpected 5% move from central bank rate decision",
        "crypto_winter": "Prolonged 30% drawdown across crypto assets",
        "black_swan": "Unexpected 20% tail event across all assets",
        "liquidity_crisis": "15% drop with widened spreads and slippage",
        "correlation_spike": "12% correlated sell-off across previously uncorrelated assets",
    }

    # Asset-type sensitivity multipliers per scenario
    SENSITIVITY: dict[str, dict[str, float]] = {
        "flash_crash": {"crypto": 1.5, "forex": 0.5, "commodity": 0.8, "equity": 1.2},
        "rate_shock": {"crypto": 0.8, "forex": 1.5, "commodity": 0.7, "equity": 1.0},
        "crypto_winter": {"crypto": 1.0, "forex": 0.1, "commodity": 0.2, "equity": 0.3},
        "black_swan": {"crypto": 1.3, "forex": 0.8, "commodity": 1.0, "equity": 1.2},
        "liquidity_crisis": {"crypto": 1.4, "forex": 0.6, "commodity": 0.9, "equity": 1.1},
        "correlation_spike": {"crypto": 1.2, "forex": 0.7, "commodity": 1.0, "equity": 1.1},
    }

    def _get_asset_type(self, symbol: str) -> str:
        """Classify a symbol to an asset type."""
        from intelligence_suite.heatmap_dashboard.portfolio_analyzer import ASSET_TYPE_MAP
        return ASSET_TYPE_MAP.get(symbol.upper(), "equity")

    def run_stress_test(
        self,
        portfolio_value: float,
        positions: list[dict[str, Any]],
    ) -> dict:
        """
        Run all stress-test scenarios against the portfolio.

        Parameters
        ----------
        portfolio_value : float
            Total portfolio value (equity).
        positions : list[dict]
            List of position dicts with at least: symbol, volume, price_current.

        Returns
        -------
        dict with per-scenario impact analysis.
        """
        results: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "portfolio_value": portfolio_value,
            "position_count": len(positions),
            "scenarios": {},
        }

        for scenario_name, base_shock in self.SCENARIOS.items():
            scenario_result = self._apply_scenario(
                scenario_name, base_shock, portfolio_value, positions
            )
            results["scenarios"][scenario_name] = scenario_result

        # Determine worst-case scenario
        worst = min(
            results["scenarios"].items(),
            key=lambda x: x[1]["portfolio_impact"],
            default=(None, {"portfolio_impact": 0}),
        )
        results["worst_case"] = {
            "scenario": worst[0],
            "impact": worst[1]["portfolio_impact"] if worst[0] else 0,
        }

        logger.info(
            f"Stress test complete: worst case = {worst[0]} "
            f"({worst[1]['portfolio_impact']:.2f})"
        )
        return results

    def _apply_scenario(
        self,
        scenario_name: str,
        base_shock: float,
        portfolio_value: float,
        positions: list[dict],
    ) -> dict:
        """Apply a single stress scenario."""
        sensitivities = self.SENSITIVITY.get(scenario_name, {})
        per_position_impact: list[dict] = []
        total_impact = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            volume = float(pos.get("volume", 0))
            price = float(pos.get("price_current", pos.get("current_price", 0)))
            notional = volume * price
            asset_type = self._get_asset_type(symbol)

            multiplier = sensitivities.get(asset_type, 1.0)
            shock = base_shock * multiplier
            impact = notional * shock

            direction = pos.get("type", "BUY")
            if direction == "SELL":
                impact = -impact  # Short positions benefit from drops

            per_position_impact.append({
                "symbol": symbol,
                "notional": round(notional, 2),
                "shock_pct": round(shock * 100, 2),
                "impact": round(impact, 2),
            })
            total_impact += impact

        return {
            "description": self.SCENARIO_DESCRIPTIONS.get(scenario_name, ""),
            "base_shock_pct": round(base_shock * 100, 2),
            "portfolio_impact": round(total_impact, 2),
            "impact_pct": round((total_impact / portfolio_value * 100) if portfolio_value else 0, 2),
            "surviving_equity": round(portfolio_value + total_impact, 2),
            "per_position": per_position_impact,
        }
