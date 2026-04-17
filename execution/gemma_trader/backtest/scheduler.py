"""
backtest/scheduler.py — drive the nightly backtest for all configured symbols.

Usage:
    python -m backtest.scheduler                  # all symbols from config.yaml
    python -m backtest.scheduler --symbol BTCUSD  # single symbol
    python -m backtest.scheduler --no-commit      # skip git auto-commit on accept

Flow per symbol:
  1. Pull historical bars from MT5.
  2. Split into IS (in-sample) and OOS (out-of-sample, last N bars).
  3. Run baseline backtest on IS+OOS separately.
  4. Call Gemma proposer on IS metrics -> <=3 proposals.
  5. Validate each proposal on OOS vs OOS baseline.
  6. Apply every accepted proposal, bump version, save rules file.
  7. Append run to logs/backtest_runs/<symbol>_<utc>.json and strategy_journal.md.
  8. If any proposal accepted: git add + commit on current branch (non-fatal on failure).
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from . import rules_loader
from .engine import run_backtest
from .proposer import propose
from .validator import validate_candidate


logger = logging.getLogger("backtest.scheduler")


APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.yaml"
RULES_PATH = APP_DIR / "strategy_rules.yaml"
RUNS_DIR = APP_DIR / "logs" / "backtest_runs"
JOURNAL_PATH = APP_DIR / "strategy_journal.md"


DEFAULT_OOS_BARS = 14 * 1440   # ~14 days of 1-min bars
DEFAULT_LOOKBACK_BARS = 60 * 1440  # ~60 days
DEFAULT_WARMUP_BARS = 300


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fetch_bars(config: dict, symbol: str, n_bars: int) -> pd.DataFrame:
    from mt5_data_feed import MT5DataFeed
    feed = MT5DataFeed(config)
    if not feed.connected:
        raise RuntimeError("MT5 not connected - start MT5 terminal first")
    feed.verify_symbols([symbol])  # auto-remap if needed
    timeframe = config.get("mt5_data", {}).get("timeframe", "1m")
    df = feed.get_candles(symbol, timeframe, n_bars)
    return df


def _ensure_seed_rules(config: dict, rules: dict) -> dict:
    """If rules file is empty / missing, seed from config defaults."""
    if rules.get("symbols"):
        return rules
    symbols = config.get("trading", {}).get("allowed_symbols", [])
    seeded = {
        "version": 1,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": {
            sym: {
                "filters": {
                    "min_adx": 20,
                    "min_vol_ratio": 1.0,
                    "required_structure": None,
                    "block_when_bb_width_below": None,
                },
                "thresholds": {
                    "min_confidence": float(config.get("trading", {}).get("confidence_threshold", 0.65)),
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "sl_atr": float(config.get("risk_management", {}).get("stop_loss_atr_multiplier", 1.0)),
                    "tp_atr": float(config.get("risk_management", {}).get("take_profit_atr_multiplier", 1.5)),
                    "cooldown_min": int(config.get("trading", {}).get("cooldown_minutes", 3)),
                },
                "baseline": {
                    "expectancy_r": None, "max_dd_r": None, "trades": None, "win_rate": None,
                },
            }
            for sym in symbols
        },
    }
    return seeded


def _journal_append(block: str) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(block)


def _git_commit(message: str) -> bool:
    """Stage strategy_rules.yaml + strategy_journal.md and commit. Non-fatal on error."""
    try:
        subprocess.run(
            ["git", "add", str(RULES_PATH), str(JOURNAL_PATH)],
            cwd=APP_DIR, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=APP_DIR, check=True, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"git commit skipped: {e.stderr.decode(errors='ignore').strip()}")
        return False
    except FileNotFoundError:
        logger.warning("git not available; skipping auto-commit")
        return False


def run_for_symbol(symbol: str, config: dict, rules: dict,
                   lookback: int, oos_bars: int) -> dict:
    logger.info(f"--- {symbol} ---")
    df = _fetch_bars(config, symbol, lookback)
    if df is None or len(df) < oos_bars + DEFAULT_WARMUP_BARS + 100:
        logger.warning(f"{symbol}: insufficient history ({len(df) if df is not None else 0} bars)")
        return {"symbol": symbol, "skipped": "insufficient_history"}

    # IS / OOS split
    df_is = df.iloc[:-oos_bars]
    df_oos = df.iloc[-oos_bars:]

    sym_rules = rules["symbols"].get(symbol, {})
    filters = sym_rules.get("filters", {}) or {}
    thresholds = sym_rules.get("thresholds", {}) or {}
    rules_block = {"filters": filters, "thresholds": thresholds}

    is_metrics = run_backtest(df_is, symbol, rules_block)
    oos_baseline = run_backtest(df_oos, symbol, rules_block)
    logger.info(f"{symbol} IS: {is_metrics['trades']} trades, exp={is_metrics['expectancy_r']:.4f}, dd={is_metrics['max_dd_r']:.4f}")
    logger.info(f"{symbol} OOS baseline: {oos_baseline['trades']} trades, exp={oos_baseline['expectancy_r']:.4f}, dd={oos_baseline['max_dd_r']:.4f}")

    # Ask Gemma for proposals (IS metrics only — OOS must not leak).
    is_summary = {k: v for k, v in is_metrics.items() if k != "trade_log"}
    proposer_out = propose(symbol, rules_block, is_summary, config)

    verdicts = []
    accepted_count = 0
    for p in proposer_out.get("proposals", []):
        v = validate_candidate(df_oos, symbol, rules_block, p, oos_baseline)
        verdicts.append({
            "proposal": p,
            "accepted": v.accepted,
            "reason": v.reason,
            "oos_candidate": {k: vv for k, vv in v.oos_candidate.items() if k != "trade_log"},
        })
        if v.accepted:
            # Apply and update rules_block live so later proposals stack cleanly.
            rules_loader.apply_proposal(rules, symbol, p["path"], p["to"])
            sym_rules = rules["symbols"][symbol]
            rules_block = {
                "filters": dict(sym_rules.get("filters") or {}),
                "thresholds": dict(sym_rules.get("thresholds") or {}),
            }
            accepted_count += 1

    # Always refresh baseline snapshot with latest OOS numbers (applied rules).
    final_oos = run_backtest(df_oos, symbol, rules_block) if accepted_count else oos_baseline
    rules_loader.update_baseline(rules, symbol, final_oos)

    return {
        "symbol": symbol,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "is_metrics": is_summary,
        "oos_baseline": {k: v for k, v in oos_baseline.items() if k != "trade_log"},
        "oos_final": {k: v for k, v in final_oos.items() if k != "trade_log"},
        "proposer": {"rationale": proposer_out.get("rationale"),
                     "n_proposed": len(proposer_out.get("proposals", []))},
        "verdicts": verdicts,
        "accepted_count": accepted_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Gemma Trader nightly backtest + rule tuner")
    parser.add_argument("--symbol", help="Single symbol (default: all from config)")
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK_BARS,
                        help=f"Bars to fetch (default {DEFAULT_LOOKBACK_BARS})")
    parser.add_argument("--oos", type=int, default=DEFAULT_OOS_BARS,
                        help=f"Bars to hold out for OOS (default {DEFAULT_OOS_BARS})")
    parser.add_argument("--no-commit", action="store_true",
                        help="Skip git auto-commit on accepted proposals")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    config = _load_config()
    rules = rules_loader.load(RULES_PATH)
    rules = _ensure_seed_rules(config, rules)

    symbols = [args.symbol] if args.symbol else config.get("trading", {}).get("allowed_symbols", [])
    if not symbols:
        logger.error("No symbols resolved")
        return 2

    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    total_accepted = 0
    summaries = []
    for sym in symbols:
        try:
            result = run_for_symbol(sym, config, rules, args.lookback, args.oos)
        except Exception as e:
            logger.error(f"{sym}: run failed: {e}", exc_info=True)
            result = {"symbol": sym, "error": str(e)}
        summaries.append(result)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RUNS_DIR / f"{sym}_{stamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        total_accepted += int(result.get("accepted_count") or 0)

        # Journal block per symbol.
        block_lines = [
            f"## {sym} — {result.get('run_utc', stamp)}",
            f"- accepted: {result.get('accepted_count', 0)}",
        ]
        if "oos_baseline" in result:
            ob = result["oos_baseline"]
            of = result["oos_final"]
            block_lines.append(
                f"- OOS baseline: trades={ob['trades']} exp={ob['expectancy_r']} dd={ob['max_dd_r']}"
            )
            block_lines.append(
                f"- OOS final:    trades={of['trades']} exp={of['expectancy_r']} dd={of['max_dd_r']}"
            )
        for v in result.get("verdicts", []):
            p = v["proposal"]
            block_lines.append(
                f"  - {'ACCEPT' if v['accepted'] else 'REJECT'} {p['path']}: {p.get('from')}->{p['to']} ({v['reason']})"
            )
        if "error" in result:
            block_lines.append(f"- ERROR: {result['error']}")
        _journal_append("\n".join(block_lines) + "\n\n")

    # Save updated rules file and optionally commit if anything was accepted.
    if total_accepted > 0:
        rules_loader.bump_version(rules)
        rules["updated_utc"] = datetime.now(timezone.utc).isoformat()
        rules_loader.save(rules, RULES_PATH)
        logger.info(f"strategy_rules.yaml bumped to v{rules['version']} ({total_accepted} accepted)")

        if not args.no_commit:
            msg_parts = [f"backtest: v{rules['version']} ({total_accepted} accepted)"]
            for s in summaries:
                if s.get("accepted_count"):
                    of = s.get("oos_final", {})
                    msg_parts.append(
                        f"  - {s['symbol']}: exp={of.get('expectancy_r')} dd={of.get('max_dd_r')}"
                    )
            _git_commit("\n".join(msg_parts))
    else:
        # Still persist the seeded file if it didn't exist before.
        if not RULES_PATH.exists():
            rules_loader.save(rules, RULES_PATH)
            logger.info("strategy_rules.yaml seeded (no accepted changes)")
        logger.info("No proposals accepted this run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
