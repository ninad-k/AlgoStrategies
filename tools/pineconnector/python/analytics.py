"""Trade analytics — PnL, win rate, drawdown calculations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import database


def get_pnl_summary(days: int = 30) -> dict[str, Any]:
    """Total and daily PnL over the given period."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    trades = _closed_trades_since(cutoff)

    total_pnl = sum(t["profit"] for t in trades)
    total_commission = sum(t.get("commission", 0) for t in trades)
    net_pnl = total_pnl - total_commission

    # Daily breakdown
    daily: dict[str, float] = {}
    for t in trades:
        day = t.get("close_time", t["open_time"])[:10]
        daily[day] = daily.get(day, 0) + t["profit"]

    # Cumulative curve
    cumulative = []
    running = 0.0
    for day in sorted(daily):
        running += daily[day]
        cumulative.append({"date": day, "pnl": round(daily[day], 2), "cumulative": round(running, 2)})

    return {
        "total_pnl": round(total_pnl, 2),
        "total_commission": round(total_commission, 2),
        "net_pnl": round(net_pnl, 2),
        "total_trades": len(trades),
        "period_days": days,
        "daily": cumulative,
    }


def get_win_rate(days: int = 30) -> dict[str, Any]:
    """Win/loss stats over the given period."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    trades = _closed_trades_since(cutoff)

    if not trades:
        return {
            "total": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "expectancy": 0,
        }

    wins = [t for t in trades if t["profit"] > 0]
    losses = [t for t in trades if t["profit"] <= 0]

    gross_profit = sum(t["profit"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["profit"] for t in losses)) if losses else 0

    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(wins) / len(trades) * 100

    expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
    }


def get_drawdown(days: int = 30) -> dict[str, Any]:
    """Max drawdown calculation over the given period."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    trades = _closed_trades_since(cutoff)

    if not trades:
        return {"max_drawdown": 0, "max_drawdown_pct": 0, "current_drawdown": 0}

    # Sort by close_time
    trades.sort(key=lambda t: t.get("close_time", t["open_time"]))

    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for t in trades:
        equity += t["profit"]
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    current_dd = peak - equity
    max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0

    return {
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 1),
        "current_drawdown": round(current_dd, 2),
        "peak_equity": round(peak, 2),
        "current_equity": round(equity, 2),
    }


def _closed_trades_since(cutoff_iso: str) -> list[dict]:
    """Fetch closed trades after a given ISO timestamp."""
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status = 'closed' AND open_time >= ? ORDER BY open_time",
            (cutoff_iso,),
        ).fetchall()
        return [dict(r) for r in rows]
