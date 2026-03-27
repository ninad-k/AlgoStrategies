"""Fetch fundamental data for a single stock via yfinance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import yfinance as yf

log = logging.getLogger(__name__)


def _pct(val) -> float | None:
    """yfinance returns margins as fractions (0.65 → 65%). Convert safely."""
    if val is None:
        return None
    try:
        return round(float(val) * 100, 1)
    except (TypeError, ValueError):
        return None


def _revenue_acceleration(ticker: yf.Ticker) -> str:
    """ACCELERATING / STABLE / DECELERATING / UNKNOWN based on quarterly YoY revenue."""
    try:
        qf = ticker.quarterly_financials
        if qf is None or qf.empty:
            return "UNKNOWN"
        rev_row = next(
            (r for r in ("Total Revenue", "Revenue", "Revenues") if r in qf.index), None
        )
        if rev_row is None:
            return "UNKNOWN"
        rev = qf.loc[rev_row].dropna().sort_index()
        if len(rev) < 5:
            return "UNKNOWN"
        growth = rev.pct_change(periods=4).dropna()
        if len(growth) < 2:
            return "UNKNOWN"
        last, prev = float(growth.iloc[-1]), float(growth.iloc[-2])
        if last > prev + 0.02:
            return "ACCELERATING"
        if last < prev - 0.02:
            return "DECELERATING"
        return "STABLE"
    except Exception:
        return "UNKNOWN"


def _eps_trend(ticker: yf.Ticker, info: dict) -> str:
    """POSITIVE / IMPROVING / STABLE / DECLINING / NEGATIVE / UNKNOWN."""
    try:
        earnings = ticker.quarterly_earnings
        if earnings is not None and not earnings.empty and "Earnings" in earnings.columns:
            eps = earnings["Earnings"].dropna()
            if len(eps) >= 2:
                recent, prev = float(eps.iloc[-1]), float(eps.iloc[-2])
                if recent > 0 and prev > 0:
                    return "POSITIVE"
                if recent > prev:
                    return "IMPROVING"
                if recent < prev:
                    return "DECLINING"
                return "NEGATIVE"
    except Exception:
        pass

    trailing_eps = info.get("trailingEps")
    if trailing_eps is not None:
        return "POSITIVE" if float(trailing_eps) > 0 else "NEGATIVE"
    return "UNKNOWN"


def _insider_activity(ticker: yf.Ticker) -> str:
    """BUYING / SELLING / NEUTRAL / UNKNOWN based on last 90 days."""
    try:
        txns = ticker.insider_transactions
        if txns is None or txns.empty:
            return "UNKNOWN"

        buys = sells = 0
        for col in ("Text", "Transaction"):
            if col in txns.columns:
                text = txns[col].astype(str).str.lower()
                buys  = text.str.contains("purchase|buy|acquisition", na=False).sum()
                sells = text.str.contains("sale|sell|disposition", na=False).sum()
                break

        if buys > sells and buys > 0:
            return "BUYING"
        if sells > buys and sells > 0:
            return "SELLING"
        return "NEUTRAL"
    except Exception:
        return "UNKNOWN"


def get_fundamental_data(symbol: str) -> dict:
    """Return a dict of fundamental metrics for `symbol`."""
    result: dict = {}
    try:
        ticker = yf.Ticker(symbol)
        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        result["company_name"] = info.get("longName") or info.get("shortName", symbol)
        result["sector"]       = info.get("sector",   "Unknown")
        result["industry"]     = info.get("industry", "Unknown")
        result["market_cap"]   = info.get("marketCap") or 0

        # Profitability
        result["gross_margin"]     = _pct(info.get("grossMargins"))
        result["operating_margin"] = _pct(info.get("operatingMargins"))
        result["profit_margin"]    = _pct(info.get("profitMargins"))
        result["roe"]              = _pct(info.get("returnOnEquity"))

        # Growth
        result["revenue_growth_yoy"] = _pct(info.get("revenueGrowth"))
        result["earnings_growth"]    = _pct(info.get("earningsGrowth"))

        # Financial health
        result["debt_equity"]    = info.get("debtToEquity")   # already a ratio * 100
        result["current_ratio"]  = info.get("currentRatio")
        result["free_cashflow"]  = info.get("freeCashflow")

        # Ownership
        result["institutional_ownership"] = _pct(info.get("institutionPercentHeld"))
        result["insider_ownership"]       = _pct(info.get("insiderPercentHeld"))
        result["short_pct_float"]         = _pct(info.get("shortPercentOfFloat"))

        # Derived signals
        result["revenue_accel"]       = _revenue_acceleration(ticker)
        result["eps_trend"]           = _eps_trend(ticker, info)
        result["insider_buy_signal"]  = _insider_activity(ticker)

    except Exception as exc:
        log.debug("Fundamental error for %s: %s", symbol, exc)

    return result
