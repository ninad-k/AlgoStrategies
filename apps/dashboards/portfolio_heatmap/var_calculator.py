"""
ReySentinel — Value at Risk (VaR) Calculator
=====================================================
Provides Historical, Parametric (Normal), and Monte Carlo VaR methods.
"""

import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VaRCalculator:
    """Calculates Value at Risk using multiple methods."""

    def historical_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
    ) -> dict:
        """
        Historical simulation VaR.

        Uses the empirical distribution of past returns to estimate the
        worst expected loss at the given confidence level.

        Parameters
        ----------
        returns : pd.Series
            Historical period returns (e.g. daily log returns).
        confidence : float
            Confidence level (0.90 to 0.99).
        portfolio_value : float
            Current portfolio value for dollar VaR.

        Returns
        -------
        dict with var_amount, var_pct, confidence, method.
        """
        if returns.empty or len(returns) < 5:
            return self._empty_result("historical", confidence)

        clean = returns.dropna()
        percentile = (1 - confidence) * 100
        var_pct = float(np.percentile(clean, percentile))
        var_amount = abs(var_pct) * portfolio_value

        logger.debug(
            f"Historical VaR: {var_pct:.4%} at {confidence:.0%} "
            f"confidence ({len(clean)} observations)"
        )
        return {
            "var_amount": round(var_amount, 2),
            "var_pct": round(var_pct, 6),
            "confidence": confidence,
            "method": "historical",
            "observations": len(clean),
        }

    def parametric_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
    ) -> dict:
        """
        Parametric (variance-covariance) VaR assuming normal distribution.

        Parameters
        ----------
        returns : pd.Series
            Historical period returns.
        confidence : float
            Confidence level.
        portfolio_value : float
            Current portfolio value.

        Returns
        -------
        dict with var_amount, var_pct, confidence, method.
        """
        if returns.empty or len(returns) < 5:
            return self._empty_result("parametric", confidence)

        clean = returns.dropna()
        mu = float(clean.mean())
        sigma = float(clean.std())

        if sigma == 0:
            return self._empty_result("parametric", confidence)

        # Z-score for the given confidence level
        from scipy import stats
        z_score = stats.norm.ppf(1 - confidence)
        var_pct = mu + z_score * sigma
        var_amount = abs(var_pct) * portfolio_value

        logger.debug(
            f"Parametric VaR: {var_pct:.4%} at {confidence:.0%} "
            f"confidence (mu={mu:.6f}, sigma={sigma:.6f})"
        )
        return {
            "var_amount": round(var_amount, 2),
            "var_pct": round(var_pct, 6),
            "confidence": confidence,
            "method": "parametric",
            "mean": round(mu, 6),
            "std": round(sigma, 6),
        }

    def monte_carlo_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
        n_simulations: int = 10000,
        horizon_days: int = 1,
    ) -> dict:
        """
        Monte Carlo simulation VaR.

        Generates random return paths from the fitted distribution and
        calculates VaR from the simulated P&L distribution.

        Parameters
        ----------
        returns : pd.Series
            Historical period returns.
        confidence : float
            Confidence level.
        portfolio_value : float
            Current portfolio value.
        n_simulations : int
            Number of Monte Carlo paths to generate.
        horizon_days : int
            Number of days to simulate forward.

        Returns
        -------
        dict with var_amount, var_pct, confidence, method.
        """
        if returns.empty or len(returns) < 5:
            return self._empty_result("monte_carlo", confidence)

        clean = returns.dropna()
        mu = float(clean.mean())
        sigma = float(clean.std())

        if sigma == 0:
            return self._empty_result("monte_carlo", confidence)

        rng = np.random.default_rng(seed=42)
        simulated = rng.normal(
            loc=mu * horizon_days,
            scale=sigma * math.sqrt(horizon_days),
            size=n_simulations,
        )

        percentile = (1 - confidence) * 100
        var_pct = float(np.percentile(simulated, percentile))
        var_amount = abs(var_pct) * portfolio_value

        logger.debug(
            f"Monte Carlo VaR: {var_pct:.4%} at {confidence:.0%} "
            f"confidence ({n_simulations} simulations)"
        )
        return {
            "var_amount": round(var_amount, 2),
            "var_pct": round(var_pct, 6),
            "confidence": confidence,
            "method": "monte_carlo",
            "n_simulations": n_simulations,
            "horizon_days": horizon_days,
        }

    @staticmethod
    def _empty_result(method: str, confidence: float) -> dict:
        """Return a zeroed-out result when data is insufficient."""
        return {
            "var_amount": 0.0,
            "var_pct": 0.0,
            "confidence": confidence,
            "method": method,
            "warning": "Insufficient data for VaR calculation",
        }
