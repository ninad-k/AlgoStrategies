# CLI: MT5 historical backtest for ML SuperTrend (cluster or ML models).
# Requires MetaTrader 5 running with a logged-in terminal session.

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.backtest_mt5 import (
    ensure_mt5,
    fetch_rates_range,
    run_cluster_backtest,
    run_ml_backtest,
    timeframe_from_string,
)
from core.supertrend_bot import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_json_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest ML SuperTrend on MT5 history")
    parser.add_argument("--symbol", default="EURUSD", help="MT5 symbol")
    parser.add_argument("--timeframe", default="M30", help="Bar timeframe (M15, M30, H1, ...)")
    parser.add_argument(
        "--mode",
        choices=("cluster", "ml"),
        default="cluster",
        help="cluster = K-Means SuperTrend bot logic; ml = trained sklearn/XGB models",
    )
    parser.add_argument("--days", type=int, default=120, help="Lookback in calendar days")
    parser.add_argument("--warmup", type=int, default=200, help="Bars skipped at start (indicators)")
    parser.add_argument("--balance", type=float, default=10_000.0, help="Starting balance (reporting)")
    parser.add_argument("--lot", type=float, default=None, help="Fixed lot size (default: symbol minimum)")
    parser.add_argument("--model-dir", default="models", help="Trained models directory (ml mode)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="ML mode: min class probability")
    parser.add_argument("--config", default="config.json", help="Optional JSON for symbol/timeframe defaults")
    parser.add_argument("--json-out", default=None, help="Write result summary to this JSON file")
    parser.add_argument(
        "--mt5-path",
        default=None,
        help="Path to terminal64.exe if initialize fails (or set MT5_TERMINAL_PATH)",
    )
    args = parser.parse_args()

    cfg_file = load_json_config(args.config)
    sym_cfg = cfg_file.get("symbols", {}).get(args.symbol, {})
    global_cfg = cfg_file.get("global_settings", {})

    tf = args.timeframe.upper()
    if sym_cfg.get("timeframe"):
        tf = sym_cfg["timeframe"].upper()

    timeframe = timeframe_from_string(tf)

    bot_cfg = Config(
        symbol=args.symbol,
        timeframe=timeframe,
        atr_period=global_cfg.get("atr_period", 10),
        min_factor=sym_cfg.get("min_factor", 1.0),
        max_factor=sym_cfg.get("max_factor", 5.0),
        factor_step=sym_cfg.get("factor_step", 0.5),
        perf_alpha=global_cfg.get("performance_alpha", 10.0),
        cluster_choice=sym_cfg.get("cluster_choice", "Average"),
        volume_ma_period=global_cfg.get("volume_ma_period", 20),
        volume_multiplier=sym_cfg.get("volume_multiplier", 1.2),
        sl_multiplier=sym_cfg.get("sl_multiplier", 2.0),
        tp_multiplier=sym_cfg.get("tp_multiplier", 3.0),
        use_trailing=global_cfg.get("use_trailing_stop", True),
        trail_activation=global_cfg.get("trail_activation_atr", 1.5),
        risk_percent=sym_cfg.get("risk_percent", 1.0),
        max_positions=global_cfg.get("max_positions_per_symbol", 1),
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    ensure_mt5(terminal_path=args.mt5_path)
    logger.info("Loading rates %s %s from %s to %s", args.symbol, tf, start.date(), end.date())
    raw = fetch_rates_range(args.symbol, timeframe, start, end)

    if args.mode == "cluster":
        stats = run_cluster_backtest(
            args.symbol,
            timeframe,
            raw,
            bot_cfg,
            initial_balance=args.balance,
            lot=args.lot,
            warmup=args.warmup,
        )
    else:
        stats = run_ml_backtest(
            args.symbol,
            timeframe,
            tf,
            raw,
            bot_cfg,
            model_dir=args.model_dir,
            initial_balance=args.balance,
            lot=args.lot,
            warmup=args.warmup,
            min_confidence=args.min_confidence,
        )

    summary = {
        "symbol": stats.symbol,
        "timeframe": stats.timeframe,
        "mode": stats.mode,
        "bars": stats.bars,
        "initial_balance": stats.initial_balance,
        "final_balance": stats.final_balance,
        "total_trades": stats.total_trades,
        "wins": stats.wins,
        "losses": stats.losses,
        "win_rate_pct": round(stats.win_rate_pct, 2),
        "profit_factor": round(stats.profit_factor, 4),
        "max_drawdown_pct": round(stats.max_drawdown_pct, 2),
        "sharpe_ratio": round(stats.sharpe_ratio, 4),
    }

    logger.info("Result: %s", json.dumps(summary, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Wrote %s", args.json_out)


if __name__ == "__main__":
    main()
