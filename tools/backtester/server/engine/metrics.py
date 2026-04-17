"""MQL5-style metrics computation from backtest results."""

from __future__ import annotations

import math
from datetime import datetime, timedelta


def compute_metrics(trades: list[dict], equity_curve: list[dict],
                    initial_capital: float, bars: int) -> dict:
    if not trades:
        return _empty_metrics(initial_capital, bars)

    profits = [t["profit"] for t in trades]
    gross_profit = sum(p for p in profits if p > 0)
    gross_loss = sum(p for p in profits if p < 0)
    net_profit = sum(profits)

    long_trades = [t for t in trades if t["direction"] == "long"]
    short_trades = [t for t in trades if t["direction"] == "short"]
    long_wins = [t for t in long_trades if t["profit"] > 0]
    short_wins = [t for t in short_trades if t["profit"] > 0]
    profit_trades = [t for t in trades if t["profit"] > 0]
    loss_trades = [t for t in trades if t["profit"] < 0]

    total = len(trades)
    n_profit = len(profit_trades)
    n_loss = len(loss_trades)

    # Profit factor (cap at 9999.99 to keep JSON-safe)
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else (
        9999.99 if gross_profit > 0 else 0
    )

    # Drawdown from equity curve
    dd = _compute_drawdown(equity_curve, initial_capital)

    # Recovery factor
    recovery_factor = (net_profit / dd["equity_dd_maximal"]) if dd["equity_dd_maximal"] > 0 else 0

    # Expected payoff
    expected_payoff = net_profit / total if total > 0 else 0

    # Sharpe ratio (annualized from trade returns)
    sharpe = _compute_sharpe(trades, initial_capital)

    # AHPR / GHPR
    ahpr, ghpr = _compute_hpr(trades, initial_capital)

    # Consecutive wins/losses
    consec = _compute_consecutive(trades)

    # Correlations
    corr = _compute_correlations(trades)

    # Holding times
    times = _compute_holding_times(trades)

    # Linear regression on equity curve
    lr = _compute_lr(equity_curve)

    # Z-Score
    z = _compute_zscore(trades)

    result = {
        "total_net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 6),
        "recovery_factor": round(recovery_factor, 6),
        "expected_payoff": round(expected_payoff, 6),
        "sharpe_ratio": round(sharpe, 5),
        "ahpr": round(ahpr, 4),
        "ahpr_pct": round((ahpr - 1) * 100, 2),
        "ghpr": round(ghpr, 4),
        "ghpr_pct": round((ghpr - 1) * 100, 2),

        **dd,

        "total_trades": total,
        "short_trades": len(short_trades),
        "short_trades_won_pct": round(len(short_wins) / len(short_trades) * 100, 2) if short_trades else 0,
        "long_trades": len(long_trades),
        "long_trades_won_pct": round(len(long_wins) / len(long_trades) * 100, 2) if long_trades else 0,
        "profit_trades": n_profit,
        "profit_trades_pct": round(n_profit / total * 100, 2) if total else 0,
        "loss_trades": n_loss,
        "loss_trades_pct": round(n_loss / total * 100, 2) if total else 0,
        "largest_profit_trade": round(max(profits), 2) if profits else 0,
        "largest_loss_trade": round(min(profits), 2) if profits else 0,
        "average_profit_trade": round(gross_profit / n_profit, 6) if n_profit else 0,
        "average_loss_trade": round(gross_loss / n_loss, 6) if n_loss else 0,

        **consec,
        **corr,
        **times,
        **lr,
        **z,

        "bars": bars,
        "total_deals": len(trades) * 2,
    }
    return _sanitize_metrics(result)


def _sanitize_metrics(m: dict) -> dict:
    """Replace inf/nan with JSON-safe values."""
    import math
    out = {}
    for k, v in m.items():
        if isinstance(v, float):
            if math.isinf(v):
                out[k] = 9999.99 if v > 0 else -9999.99
            elif math.isnan(v):
                out[k] = 0.0
            else:
                out[k] = v
        else:
            out[k] = v
    return out


def _empty_metrics(initial_capital: float, bars: int) -> dict:
    return {
        "total_net_profit": 0, "gross_profit": 0, "gross_loss": 0,
        "profit_factor": 0, "recovery_factor": 0, "expected_payoff": 0,
        "sharpe_ratio": 0, "ahpr": 1, "ahpr_pct": 0, "ghpr": 1, "ghpr_pct": 0,
        "balance_dd_absolute": 0, "balance_dd_maximal": 0, "balance_dd_maximal_pct": 0,
        "balance_dd_relative_pct": 0, "balance_dd_relative_val": 0,
        "equity_dd_absolute": 0, "equity_dd_maximal": 0, "equity_dd_maximal_pct": 0,
        "equity_dd_relative_pct": 0, "equity_dd_relative_val": 0,
        "total_trades": 0, "short_trades": 0, "short_trades_won_pct": 0,
        "long_trades": 0, "long_trades_won_pct": 0, "profit_trades": 0,
        "profit_trades_pct": 0, "loss_trades": 0, "loss_trades_pct": 0,
        "largest_profit_trade": 0, "largest_loss_trade": 0,
        "average_profit_trade": 0, "average_loss_trade": 0,
        "max_consecutive_wins": 0, "max_consecutive_wins_money": 0,
        "max_consecutive_losses": 0, "max_consecutive_losses_money": 0,
        "max_consecutive_profit": 0, "max_consecutive_profit_count": 0,
        "max_consecutive_loss": 0, "max_consecutive_loss_count": 0,
        "avg_consecutive_wins": 0, "avg_consecutive_losses": 0,
        "corr_profits_mfe": 0, "corr_profits_mae": 0, "corr_mfe_mae": 0,
        "min_holding_time": "", "max_holding_time": "", "avg_holding_time": "",
        "lr_correlation": 0, "lr_standard_error": 0,
        "z_score": 0, "z_score_pct": 0,
        "bars": bars, "total_deals": 0,
    }


def _compute_drawdown(equity_curve: list[dict], initial_capital: float) -> dict:
    if not equity_curve:
        return {
            "balance_dd_absolute": 0, "balance_dd_maximal": 0, "balance_dd_maximal_pct": 0,
            "balance_dd_relative_pct": 0, "balance_dd_relative_val": 0,
            "equity_dd_absolute": 0, "equity_dd_maximal": 0, "equity_dd_maximal_pct": 0,
            "equity_dd_relative_pct": 0, "equity_dd_relative_val": 0,
        }

    balances = [p["balance"] for p in equity_curve]
    equities = [p.get("equity", p["balance"]) for p in equity_curve]

    bal_dd = _dd_stats(balances, initial_capital)
    eq_dd = _dd_stats(equities, initial_capital)

    return {
        "balance_dd_absolute": round(bal_dd["absolute"], 2),
        "balance_dd_maximal": round(bal_dd["maximal"], 2),
        "balance_dd_maximal_pct": round(bal_dd["maximal_pct"], 2),
        "balance_dd_relative_pct": round(bal_dd["relative_pct"], 2),
        "balance_dd_relative_val": round(bal_dd["relative_val"], 2),
        "equity_dd_absolute": round(eq_dd["absolute"], 2),
        "equity_dd_maximal": round(eq_dd["maximal"], 2),
        "equity_dd_maximal_pct": round(eq_dd["maximal_pct"], 2),
        "equity_dd_relative_pct": round(eq_dd["relative_pct"], 2),
        "equity_dd_relative_val": round(eq_dd["relative_val"], 2),
    }


def _dd_stats(values: list[float], initial: float) -> dict:
    if not values:
        return {"absolute": 0, "maximal": 0, "maximal_pct": 0, "relative_pct": 0, "relative_val": 0}

    peak = initial
    max_dd = 0
    max_dd_pct = 0
    min_val = initial

    max_rel_pct = 0
    max_rel_val = 0

    for v in values:
        if v > peak:
            peak = v
        dd = peak - v
        dd_pct = (dd / peak * 100) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
        if dd_pct > max_rel_pct:
            max_rel_pct = dd_pct
            max_rel_val = dd
        min_val = min(min_val, v)

    absolute = initial - min_val if min_val < initial else 0

    return {
        "absolute": absolute,
        "maximal": max_dd,
        "maximal_pct": max_dd_pct,
        "relative_pct": max_rel_pct,
        "relative_val": max_rel_val,
    }


def _compute_sharpe(trades: list[dict], initial_capital: float) -> float:
    if len(trades) < 2:
        return 0
    returns = [t["profit"] / initial_capital for t in trades]
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var) if var > 0 else 0
    if std == 0:
        return 0
    return (mean_r / std) * math.sqrt(252)


def _compute_hpr(trades: list[dict], initial_capital: float) -> tuple[float, float]:
    if not trades:
        return 1.0, 1.0
    capital = initial_capital
    hprs = []
    for t in trades:
        if capital > 0:
            hpr = 1 + t["profit"] / capital
            hprs.append(hpr)
            capital += t["profit"]
    if not hprs:
        return 1.0, 1.0
    ahpr = sum(hprs) / len(hprs)
    log_sum = sum(math.log(max(h, 0.0001)) for h in hprs)
    ghpr = math.exp(log_sum / len(hprs))
    return ahpr, ghpr


def _compute_consecutive(trades: list[dict]) -> dict:
    if not trades:
        return {
            "max_consecutive_wins": 0, "max_consecutive_wins_money": 0,
            "max_consecutive_losses": 0, "max_consecutive_losses_money": 0,
            "max_consecutive_profit": 0, "max_consecutive_profit_count": 0,
            "max_consecutive_loss": 0, "max_consecutive_loss_count": 0,
            "avg_consecutive_wins": 0, "avg_consecutive_losses": 0,
        }

    streaks_win = []
    streaks_loss = []
    cur_wins = 0
    cur_win_money = 0
    cur_losses = 0
    cur_loss_money = 0

    for t in trades:
        if t["profit"] > 0:
            cur_wins += 1
            cur_win_money += t["profit"]
            if cur_losses > 0:
                streaks_loss.append((cur_losses, cur_loss_money))
                cur_losses = 0
                cur_loss_money = 0
        elif t["profit"] < 0:
            cur_losses += 1
            cur_loss_money += t["profit"]
            if cur_wins > 0:
                streaks_win.append((cur_wins, cur_win_money))
                cur_wins = 0
                cur_win_money = 0

    if cur_wins > 0:
        streaks_win.append((cur_wins, cur_win_money))
    if cur_losses > 0:
        streaks_loss.append((cur_losses, cur_loss_money))

    max_win_streak = max(streaks_win, key=lambda x: x[0]) if streaks_win else (0, 0)
    max_loss_streak = max(streaks_loss, key=lambda x: x[0]) if streaks_loss else (0, 0)
    max_profit_streak = max(streaks_win, key=lambda x: x[1]) if streaks_win else (0, 0)
    max_loss_money_streak = min(streaks_loss, key=lambda x: x[1]) if streaks_loss else (0, 0)

    avg_w = sum(s[0] for s in streaks_win) / len(streaks_win) if streaks_win else 0
    avg_l = sum(s[0] for s in streaks_loss) / len(streaks_loss) if streaks_loss else 0

    return {
        "max_consecutive_wins": max_win_streak[0],
        "max_consecutive_wins_money": round(max_win_streak[1], 2),
        "max_consecutive_losses": max_loss_streak[0],
        "max_consecutive_losses_money": round(max_loss_streak[1], 2),
        "max_consecutive_profit": round(max_profit_streak[1], 2),
        "max_consecutive_profit_count": max_profit_streak[0],
        "max_consecutive_loss": round(max_loss_money_streak[1], 2),
        "max_consecutive_loss_count": max_loss_money_streak[0],
        "avg_consecutive_wins": round(avg_w, 0),
        "avg_consecutive_losses": round(avg_l, 0),
    }


def _compute_correlations(trades: list[dict]) -> dict:
    profits = [t["profit"] for t in trades]
    mfes = [t.get("mfe", 0) for t in trades]
    maes = [t.get("mae", 0) for t in trades]

    return {
        "corr_profits_mfe": round(_pearson(profits, mfes), 6),
        "corr_profits_mae": round(_pearson(profits, maes), 6),
        "corr_mfe_mae": round(_pearson(mfes, maes), 6),
    }


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2:
        return 0
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return 0
    return cov / (sx * sy)


def _compute_holding_times(trades: list[dict]) -> dict:
    durations = []
    for t in trades:
        try:
            open_t = datetime.fromisoformat(t["open_time"])
            close_t = datetime.fromisoformat(t["close_time"])
            durations.append(close_t - open_t)
        except (ValueError, KeyError):
            continue

    if not durations:
        return {"min_holding_time": "", "max_holding_time": "", "avg_holding_time": ""}

    min_d = min(durations)
    max_d = max(durations)
    avg_d = sum(durations, timedelta()) / len(durations)

    return {
        "min_holding_time": _format_td(min_d),
        "max_holding_time": _format_td(max_d),
        "avg_holding_time": _format_td(avg_d),
    }


def _format_td(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def _compute_lr(equity_curve: list[dict]) -> dict:
    if len(equity_curve) < 3:
        return {"lr_correlation": 0, "lr_standard_error": 0}

    y = [p["balance"] for p in equity_curve]
    n = len(y)
    x = list(range(n))

    mx = sum(x) / n
    my = sum(y) / n

    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_yy = sum((yi - my) ** 2 for yi in y)

    if ss_xx == 0 or ss_yy == 0:
        return {"lr_correlation": 0, "lr_standard_error": 0}

    r = ss_xy / math.sqrt(ss_xx * ss_yy)

    b = ss_xy / ss_xx
    a = my - b * mx
    residuals = [(yi - (a + b * xi)) ** 2 for xi, yi in zip(x, y)]
    se = math.sqrt(sum(residuals) / (n - 2)) if n > 2 else 0

    return {
        "lr_correlation": round(r, 6),
        "lr_standard_error": round(se, 6),
    }


def _compute_zscore(trades: list[dict]) -> dict:
    if len(trades) < 3:
        return {"z_score": 0, "z_score_pct": 0}

    n = len(trades)
    wins = sum(1 for t in trades if t["profit"] > 0)
    losses = n - wins

    if wins == 0 or losses == 0:
        return {"z_score": 0, "z_score_pct": 0}

    runs = 1
    for i in range(1, n):
        if (trades[i]["profit"] > 0) != (trades[i - 1]["profit"] > 0):
            runs += 1

    p = wins / n
    q = losses / n
    expected_runs = 1 + 2 * n * p * q
    variance = 2 * n * p * q * (2 * n * p * q - n) / (n * n - n + 0.0001)
    std_runs = math.sqrt(max(variance, 0))

    if std_runs == 0:
        return {"z_score": 0, "z_score_pct": 0}

    z = (runs - expected_runs) / std_runs

    # Approximate two-tailed p-value from z
    p_val = math.erfc(abs(z) / math.sqrt(2)) * 100

    return {
        "z_score": round(z, 2),
        "z_score_pct": round(p_val, 2),
    }
