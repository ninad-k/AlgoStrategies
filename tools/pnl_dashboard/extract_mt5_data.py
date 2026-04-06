"""
MT5 Data Extraction Script
Connects to multiple MT5 accounts via MetaTrader5 Python API,
extracts deal history, pairs deals into trades, calculates MFE/MAE,
and exports per-account CSVs.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("extract_mt5_data")

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "accounts.yaml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    # Resolve env-var passwords
    for acct in cfg.get("accounts", []):
        pw = acct.get("password", "")
        if pw.startswith("${") and pw.endswith("}"):
            env_key = pw[2:-1]
            acct["password"] = os.environ.get(env_key, "")
            if not acct["password"]:
                logger.warning("Environment variable %s not set for account %s", env_key, acct["login"])
    return cfg


def connect_mt5(account: dict) -> bool:
    if not mt5.initialize(
        path=account.get("path"),
        login=int(account["login"]),
        password=account["password"],
        server=account["server"],
    ):
        logger.error("MT5 init failed for %s: %s", account["login"], mt5.last_error())
        return False
    info = mt5.account_info()
    if info is None:
        logger.error("Cannot get account info for %s", account["login"])
        mt5.shutdown()
        return False
    logger.info("Connected: %s (%s) Balance=%.2f %s", info.name, info.server, info.balance, info.currency)
    return True


def pair_deals(deals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Group deals by position_id, match DEAL_ENTRY_IN with DEAL_ENTRY_OUT.
    Handles partial closes (multiple exits per position).
    """
    if deals_df.empty:
        return pd.DataFrame()

    entries = deals_df[deals_df["entry"] == mt5.DEAL_ENTRY_IN].copy()
    exits = deals_df[deals_df["entry"] == mt5.DEAL_ENTRY_OUT].copy()

    trades = []
    for pos_id, entry_group in entries.groupby("position_id"):
        entry = entry_group.iloc[0]
        pos_exits = exits[exits["position_id"] == pos_id]

        if pos_exits.empty:
            # Still-open position
            trades.append({
                "ticket": int(entry["position_id"]),
                "deal_entry_ticket": int(entry["ticket"]),
                "deal_exit_ticket": 0,
                "symbol": entry["symbol"],
                "direction": 0 if entry["type"] == mt5.DEAL_TYPE_BUY else 1,
                "magic_number": int(entry["magic"]),
                "volume": float(entry["volume"]),
                "entry_price": float(entry["price"]),
                "exit_price": 0.0,
                "sl": 0.0,
                "tp": 0.0,
                "entry_time": datetime.utcfromtimestamp(entry["time"]).strftime("%Y-%m-%d %H:%M:%S"),
                "exit_time": None,
                "profit_loss": float(entry.get("profit", 0)),
                "commission": float(entry.get("commission", 0)),
                "swap": float(entry.get("swap", 0)),
                "comment": str(entry.get("comment", "")),
                "is_open": 1,
                "holding_time_minutes": 0.0,
            })
        else:
            for _, ex in pos_exits.iterrows():
                entry_ts = int(entry["time"])
                exit_ts = int(ex["time"])
                holding_min = (exit_ts - entry_ts) / 60.0
                trades.append({
                    "ticket": int(entry["position_id"]),
                    "deal_entry_ticket": int(entry["ticket"]),
                    "deal_exit_ticket": int(ex["ticket"]),
                    "symbol": entry["symbol"],
                    "direction": 0 if entry["type"] == mt5.DEAL_TYPE_BUY else 1,
                    "magic_number": int(entry["magic"]),
                    "volume": float(ex["volume"]),
                    "entry_price": float(entry["price"]),
                    "exit_price": float(ex["price"]),
                    "sl": 0.0,
                    "tp": 0.0,
                    "entry_time": datetime.utcfromtimestamp(entry_ts).strftime("%Y-%m-%d %H:%M:%S"),
                    "exit_time": datetime.utcfromtimestamp(exit_ts).strftime("%Y-%m-%d %H:%M:%S"),
                    "profit_loss": float(ex.get("profit", 0)),
                    "commission": float(entry.get("commission", 0)) + float(ex.get("commission", 0)),
                    "swap": float(ex.get("swap", 0)),
                    "comment": str(entry.get("comment", "")),
                    "is_open": 0,
                    "holding_time_minutes": holding_min,
                })

    return pd.DataFrame(trades)


def calculate_mfe_mae(trades_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Maximum Favorable Excursion and Maximum Adverse Excursion
    using M1 candle data between entry and exit times.
    """
    if trades_df.empty:
        return trades_df

    mfe_values = []
    mae_values = []

    for _, trade in trades_df.iterrows():
        if trade["is_open"] == 1 or not trade["exit_time"]:
            mfe_values.append(None)
            mae_values.append(None)
            continue

        entry_dt = datetime.strptime(trade["entry_time"], "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.strptime(trade["exit_time"], "%Y-%m-%d %H:%M:%S")

        rates = mt5.copy_rates_range(trade["symbol"], mt5.TIMEFRAME_M1, entry_dt, exit_dt)
        if rates is None or len(rates) == 0:
            mfe_values.append(None)
            mae_values.append(None)
            continue

        rates_df = pd.DataFrame(rates)
        entry_price = trade["entry_price"]

        if trade["direction"] == 0:  # Buy
            mfe = float(rates_df["high"].max()) - entry_price
            mae = entry_price - float(rates_df["low"].min())
        else:  # Sell
            mfe = entry_price - float(rates_df["low"].min())
            mae = float(rates_df["high"].max()) - entry_price

        mfe_values.append(round(mfe, 5))
        mae_values.append(round(mae, 5))

    trades_df["mfe"] = mfe_values
    trades_df["mae"] = mae_values
    return trades_df


def extract_account(account: dict, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Extract all deals from one MT5 account, pair them, and calculate MFE/MAE."""
    if not connect_mt5(account):
        return pd.DataFrame()

    try:
        deals = mt5.history_deals_get(start_date, end_date)
        if deals is None or len(deals) == 0:
            logger.warning("No deals found for account %s", account["login"])
            return pd.DataFrame()

        deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        logger.info("Account %s: %d raw deals fetched", account["login"], len(deals_df))

        # Filter to trade deals only (exclude balance, credit, etc.)
        trade_types = [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]
        deals_df = deals_df[deals_df["type"].isin(trade_types)]

        paired = pair_deals(deals_df)
        if paired.empty:
            logger.warning("No paired trades for account %s", account["login"])
            return pd.DataFrame()

        paired = calculate_mfe_mae(paired)

        # Add account metadata
        info = mt5.account_info()
        paired["account_login"] = int(account["login"])
        paired["account_server"] = account["server"]
        paired["account_name"] = info.name if info else ""
        paired["account_currency"] = info.currency if info else "USD"
        paired["trader"] = account.get("trader", "")

        logger.info("Account %s: %d trades paired", account["login"], len(paired))
        return paired

    finally:
        mt5.shutdown()


def export_to_csv(trades_df: pd.DataFrame, account_login: int, export_dir: Path):
    """Save trades DataFrame as CSV."""
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = export_dir / f"trades_{account_login}_{ts}.csv"
    trades_df.to_csv(filename, index=False)
    logger.info("Exported %d trades to %s", len(trades_df), filename)
    return filename


def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    cfg = load_config(config_path)

    export_dir = Path(cfg.get("export_dir", "./data/mt5_exports"))
    start_date = datetime.strptime(cfg.get("start_date", "2020-01-01"), "%Y-%m-%d")
    end_date = datetime.now() + timedelta(days=1)

    all_trades = []
    for account in cfg.get("accounts", []):
        logger.info("Processing account %s (%s)...", account["login"], account.get("label", ""))
        trades = extract_account(account, start_date, end_date)
        if not trades.empty:
            export_to_csv(trades, account["login"], export_dir)
            all_trades.append(trades)

    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        combined_path = export_dir / f"all_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        combined.to_csv(combined_path, index=False)
        logger.info("Combined export: %d trades to %s", len(combined), combined_path)
    else:
        logger.warning("No trades extracted from any account")


if __name__ == "__main__":
    main()
