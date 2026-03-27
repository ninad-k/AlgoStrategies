"""Chart data preparation for the frontend."""

from __future__ import annotations


def prepare_equity_chart(equity_curve: list[dict]) -> dict:
    return {
        "labels": [p["timestamp"] for p in equity_curve],
        "balance": [p["balance"] for p in equity_curve],
        "equity": [p.get("equity", p["balance"]) for p in equity_curve],
    }


def prepare_drawdown_chart(equity_curve: list[dict]) -> dict:
    return {
        "labels": [p["timestamp"] for p in equity_curve],
        "drawdown_pct": [p.get("drawdown_pct", 0) for p in equity_curve],
    }


def prepare_profit_distribution(trades: list[dict]) -> dict:
    profits = [t["profit"] for t in trades]
    if not profits:
        return {"bins": [], "counts": []}

    min_p = min(profits)
    max_p = max(profits)
    if min_p == max_p:
        return {"bins": [min_p], "counts": [len(profits)]}

    n_bins = min(30, max(10, len(profits) // 5))
    bin_width = (max_p - min_p) / n_bins
    bins = [min_p + i * bin_width for i in range(n_bins + 1)]
    counts = [0] * n_bins

    for p in profits:
        idx = int((p - min_p) / bin_width)
        idx = min(idx, n_bins - 1)
        counts[idx] += 1

    bin_labels = [round((bins[i] + bins[i + 1]) / 2, 2) for i in range(n_bins)]
    return {"bins": bin_labels, "counts": counts}


def prepare_monthly_returns(trades: list[dict], initial_capital: float) -> list[dict]:
    if not trades:
        return []

    monthly = {}
    for t in trades:
        try:
            month_key = t["close_time"][:7]  # YYYY-MM
        except (KeyError, IndexError):
            continue
        monthly.setdefault(month_key, 0)
        monthly[month_key] += t["profit"]

    result = []
    for month, profit in sorted(monthly.items()):
        result.append({
            "month": month,
            "profit": round(profit, 2),
            "return_pct": round(profit / initial_capital * 100, 2),
        })
    return result
