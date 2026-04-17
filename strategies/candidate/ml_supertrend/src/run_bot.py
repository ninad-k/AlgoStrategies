# ML-SuperTrend Bot Runner
# Author: Ninad
#
# CLI entry point: loads config.json, connects to MT5, and runs the bot.

import argparse
import json
import logging
import MetaTrader5 as mt5
from core.supertrend_bot import SuperTrendBot, Config

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1,
}


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="ML-SuperTrend Trading Bot")
    parser.add_argument("--account", default="demo", help="Account name from config.json")
    parser.add_argument("--symbol", default=None, help="Override trading symbol")
    parser.add_argument("--dry-run", action="store_true", help="Log signals without placing orders")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    raw = load_config()
    account = raw["accounts"][args.account]

    if not mt5.initialize():
        logging.error("MT5 initialization failed")
        return

    if not mt5.login(account["login"], password=account["password"], server=account["server"]):
        logging.error(f"Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    symbols_cfg = raw.get("symbols", {})
    global_cfg = raw.get("global_settings", {})

    for symbol, sym_cfg in symbols_cfg.items():
        if not sym_cfg.get("enabled", True):
            continue
        if args.symbol and symbol != args.symbol:
            continue

        config = Config(
            symbol=symbol,
            timeframe=TIMEFRAME_MAP.get(sym_cfg.get("timeframe", "M30"), mt5.TIMEFRAME_M30),
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

        bot = SuperTrendBot(config)
        bot.is_connected = True
        logging.info(f"Starting bot for {symbol}")
        bot.run(interval_seconds=60)

    mt5.shutdown()


if __name__ == "__main__":
    main()
