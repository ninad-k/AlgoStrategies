"""Normalise raw MT5 paired-deals data into the journal's canonical DataFrame.

Input (from apps/tools/pnl_dashboard/extract_mt5_data.py pair_deals + MFE/MAE
enrichment, plus account metadata): columns include ticket, symbol, direction,
magic_number, volume, entry_price, exit_price, sl, tp, entry_time, exit_time,
profit_loss, commission, swap, comment, is_open, holding_time_minutes, mfe,
mae, account_login, account_server, account_name, account_currency, trader.

Output: a DataFrame suitable for direct consumption by journal_writer, with
scalping-specific enrichment (session, hour-of-day, holding buckets, pip move,
efficiency ratios).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd


HOLDING_BUCKETS = [
    ("<30s", 0, 30),
    ("30s-2m", 30, 120),
    ("2-5m", 120, 300),
    ("5-15m", 300, 900),
    ("15m+", 900, float("inf")),
]


def _pip_size(symbol: str) -> float:
    """Best-effort pip size for common symbols. Unknown -> NaN."""
    if not isinstance(symbol, str):
        return float("nan")
    s = symbol.upper()
    if s.endswith("JPY"):
        return 0.01
    if s.startswith(("XAU", "XAG")) or s in {"GOLD", "SILVER"}:
        return 0.1
    if any(idx in s for idx in ("US30", "US500", "NAS100", "US100", "GER40", "UK100", "JP225", "SPX", "NDX")):
        return 1.0
    if s.startswith(("BTC", "ETH", "XRP", "SOL", "LTC")):
        return 1.0
    # Default FX major/minor
    if len(s) == 6 and s.isalpha():
        return 0.0001
    return float("nan")


def _session(hour: int) -> str:
    """UTC-hour -> trading session bucket."""
    if hour >= 22 or hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 16:
        return "London-NY Overlap"
    if 16 <= hour < 21:
        return "New York"
    return "Gap"


def _holding_bucket(seconds: float) -> str:
    if pd.isna(seconds):
        return ""
    for label, lo, hi in HOLDING_BUCKETS:
        if lo <= seconds < hi:
            return label
    return ""


def _parse_dt(val) -> pd.Timestamp:
    if isinstance(val, pd.Timestamp):
        return val
    if val is None or val == "" or (isinstance(val, float) and np.isnan(val)):
        return pd.NaT
    return pd.to_datetime(val, errors="coerce")


def normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """Take raw paired-deals dataframe and return the canonical journal frame."""
    if raw.empty:
        return pd.DataFrame()

    df = raw.copy()

    # Only closed trades belong in the journal.
    if "is_open" in df.columns:
        df = df[df["is_open"] == 0].copy()
    if df.empty:
        return pd.DataFrame()

    df["entry_time"] = df["entry_time"].apply(_parse_dt)
    df["exit_time"] = df["exit_time"].apply(_parse_dt)

    df["holding_seconds"] = (df["exit_time"] - df["entry_time"]).dt.total_seconds()
    df["date"] = df["exit_time"].dt.date
    df["hour_of_day"] = df["exit_time"].dt.hour
    df["weekday"] = df["exit_time"].dt.day_name()
    df["session"] = df["hour_of_day"].apply(_session)
    df["holding_bucket"] = df["holding_seconds"].apply(_holding_bucket)

    df["direction_str"] = np.where(df["direction"] == 0, "Buy", "Sell")
    df["sign"] = np.where(df["direction"] == 0, 1.0, -1.0)
    df["price_move"] = (df["exit_price"] - df["entry_price"]) * df["sign"]
    df["pip_size"] = df["symbol"].apply(_pip_size)
    df["pips"] = df["price_move"] / df["pip_size"]

    df["net_profit"] = df["profit_loss"].fillna(0) + df["commission"].fillna(0) + df["swap"].fillna(0)
    df["is_win"] = df["net_profit"] > 0

    # MFE / MAE efficiency: realised move as a share of max favourable excursion.
    mfe = df.get("mfe")
    if mfe is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            df["mfe_efficiency"] = np.where(
                (mfe.notna()) & (mfe > 0),
                df["price_move"].clip(lower=0) / mfe,
                np.nan,
            )
    else:
        df["mfe_efficiency"] = np.nan
        df["mfe"] = np.nan
        df["mae"] = np.nan

    account_id = df.get("account_login", pd.Series(["UNKNOWN"] * len(df))).astype(str)
    account_label = df.get("account_name", pd.Series([""] * len(df))).astype(str)
    df["account_id"] = account_id
    df["account_label"] = np.where(account_label.str.len() > 0, account_label, account_id)

    # R-multiple: only meaningful when sl was recorded. pair_deals currently
    # leaves sl as 0.0, so this column will typically be NaN. We preserve the
    # calculation so that once sl is populated upstream, it starts working.
    sl = df.get("sl", pd.Series([0.0] * len(df)))
    with np.errstate(divide="ignore", invalid="ignore"):
        risk_move = np.abs(df["entry_price"] - sl) * np.where(sl > 0, 1.0, np.nan)
        df["r_multiple"] = df["price_move"] / risk_move

    canonical_cols = [
        "account_id", "account_label", "ticket", "magic_number",
        "symbol", "direction_str", "volume",
        "entry_time", "exit_time", "holding_seconds", "holding_bucket",
        "entry_price", "exit_price", "sl", "tp",
        "price_move", "pips",
        "profit_loss", "commission", "swap", "net_profit", "is_win",
        "mfe", "mae", "mfe_efficiency", "r_multiple",
        "session", "hour_of_day", "weekday", "date",
        "comment",
    ]
    available = [c for c in canonical_cols if c in df.columns]
    out = df[available].copy()
    out = out.sort_values("exit_time").reset_index(drop=True)
    return out


@dataclass
class JournalStats:
    """Key portfolio metrics used on summary sheets."""
    trades: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    expectancy: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    max_drawdown: float
    max_consec_losses: int
    sharpe_of_trades: float
    sl_hit_pct: float
    tp_hit_pct: float
    commission_drag_pct: float

    @staticmethod
    def compute(df: pd.DataFrame) -> "JournalStats":
        if df.empty:
            return JournalStats(
                trades=0, wins=0, losses=0, win_rate=0.0,
                gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
                profit_factor=0.0, expectancy=0.0,
                avg_win=0.0, avg_loss=0.0,
                best_trade=0.0, worst_trade=0.0,
                max_drawdown=0.0, max_consec_losses=0,
                sharpe_of_trades=0.0,
                sl_hit_pct=0.0, tp_hit_pct=0.0, commission_drag_pct=0.0,
            )

        wins_mask = df["is_win"]
        wins = int(wins_mask.sum())
        losses = int((~wins_mask).sum())
        trades = len(df)
        gross_profit = float(df.loc[wins_mask, "net_profit"].sum())
        gross_loss = float(df.loc[~wins_mask, "net_profit"].sum())  # negative
        net_profit = float(df["net_profit"].sum())
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else float("inf")
        expectancy = net_profit / trades if trades else 0.0
        avg_win = float(df.loc[wins_mask, "net_profit"].mean()) if wins else 0.0
        avg_loss = float(df.loc[~wins_mask, "net_profit"].mean()) if losses else 0.0
        best_trade = float(df["net_profit"].max())
        worst_trade = float(df["net_profit"].min())

        equity = df["net_profit"].cumsum()
        running_peak = equity.cummax()
        drawdown = equity - running_peak
        max_drawdown = float(drawdown.min())

        # Max consecutive losses (streak of non-wins).
        streak = 0
        max_streak = 0
        for w in wins_mask:
            if not w:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        returns = df["net_profit"]
        std = float(returns.std(ddof=0))
        sharpe = float(returns.mean() / std) if std > 0 else 0.0

        # SL / TP hit heuristic: within a few pips of the recorded level at exit.
        sl_hits = 0
        tp_hits = 0
        if "sl" in df.columns and "tp" in df.columns:
            for _, row in df.iterrows():
                pip = row.get("pip_size") or _pip_size(row.get("symbol", ""))
                tol = 3 * pip if pd.notna(pip) else 0
                sl = row.get("sl", 0) or 0
                tp = row.get("tp", 0) or 0
                ex = row.get("exit_price", 0) or 0
                if sl > 0 and tol and abs(ex - sl) <= tol:
                    sl_hits += 1
                if tp > 0 and tol and abs(ex - tp) <= tol:
                    tp_hits += 1

        commission_total = float(df.get("commission", pd.Series([0])).sum() + df.get("swap", pd.Series([0])).sum())
        gross_before_costs = net_profit - commission_total
        commission_drag_pct = (
            abs(commission_total) / abs(gross_before_costs) if gross_before_costs else 0.0
        )

        return JournalStats(
            trades=trades, wins=wins, losses=losses,
            win_rate=wins / trades if trades else 0.0,
            gross_profit=gross_profit, gross_loss=gross_loss,
            net_profit=net_profit,
            profit_factor=profit_factor, expectancy=expectancy,
            avg_win=avg_win, avg_loss=avg_loss,
            best_trade=best_trade, worst_trade=worst_trade,
            max_drawdown=max_drawdown, max_consec_losses=max_streak,
            sharpe_of_trades=sharpe,
            sl_hit_pct=(sl_hits / trades) if trades else 0.0,
            tp_hit_pct=(tp_hits / trades) if trades else 0.0,
            commission_drag_pct=commission_drag_pct,
        )


def daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("date", sort=True)
    rows = []
    running_equity = 0.0
    for date, grp in g:
        stats = JournalStats.compute(grp)
        running_equity += stats.net_profit
        rows.append({
            "date": date,
            "trades": stats.trades,
            "wins": stats.wins,
            "losses": stats.losses,
            "win_rate": stats.win_rate,
            "gross_profit": stats.gross_profit,
            "gross_loss": stats.gross_loss,
            "net_profit": stats.net_profit,
            "expectancy": stats.expectancy,
            "profit_factor": stats.profit_factor,
            "avg_holding_seconds": float(grp["holding_seconds"].mean()) if len(grp) else 0.0,
            "best_trade": stats.best_trade,
            "worst_trade": stats.worst_trade,
            "running_equity": running_equity,
        })
    return pd.DataFrame(rows)


def _bucket_stats(df: pd.DataFrame, bucket_col: str, bucket_order: Iterable | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    rows = []
    groups = df.groupby(bucket_col, dropna=False)
    for key, grp in groups:
        stats = JournalStats.compute(grp)
        rows.append({
            bucket_col: key if pd.notna(key) else "",
            "trades": stats.trades,
            "wins": stats.wins,
            "win_rate": stats.win_rate,
            "net_profit": stats.net_profit,
            "expectancy": stats.expectancy,
            "profit_factor": stats.profit_factor,
            "avg_holding_seconds": float(grp["holding_seconds"].mean()) if len(grp) else 0.0,
        })
    out = pd.DataFrame(rows)
    if bucket_order is not None:
        order_map = {k: i for i, k in enumerate(bucket_order)}
        out["_ord"] = out[bucket_col].map(lambda v: order_map.get(v, len(order_map)))
        out = out.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    else:
        out = out.sort_values(bucket_col).reset_index(drop=True)
    return out


def by_hour(df: pd.DataFrame) -> pd.DataFrame:
    return _bucket_stats(df, "hour_of_day", bucket_order=list(range(24)))


def by_session(df: pd.DataFrame) -> pd.DataFrame:
    return _bucket_stats(df, "session", bucket_order=["Asia", "London", "London-NY Overlap", "New York", "Gap"])


def by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    return _bucket_stats(
        df, "weekday",
        bucket_order=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    )


def by_symbol(df: pd.DataFrame) -> pd.DataFrame:
    return _bucket_stats(df, "symbol")


def by_account(df: pd.DataFrame) -> pd.DataFrame:
    return _bucket_stats(df, "account_id")


def by_holding_bucket(df: pd.DataFrame) -> pd.DataFrame:
    order = [b[0] for b in HOLDING_BUCKETS]
    return _bucket_stats(df, "holding_bucket", bucket_order=order)


def calendar_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Wide date grid: index=ISO week, columns=weekday, values=daily net P&L."""
    if df.empty:
        return pd.DataFrame()
    daily = df.groupby("date", as_index=False)["net_profit"].sum()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["iso_week"] = daily["date"].dt.strftime("%G-W%V")
    daily["weekday"] = daily["date"].dt.day_name()
    pivot = daily.pivot_table(index="iso_week", columns="weekday", values="net_profit", aggfunc="sum")
    ordered_cols = [d for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] if d in pivot.columns]
    return pivot[ordered_cols].reset_index()


def metric_dt_range(df: pd.DataFrame) -> tuple[datetime | None, datetime | None]:
    if df.empty:
        return None, None
    return df["exit_time"].min(), df["exit_time"].max()
