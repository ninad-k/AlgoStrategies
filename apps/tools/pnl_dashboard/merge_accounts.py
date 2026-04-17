"""
Merge Accounts Script
Reads CSV exports and/or existing SQLite data, merges by composite key
(account_login, ticket, deal_exit_ticket), handles INSERT/UPDATE/SKIP logic,
tracks sync history.
"""
import os
import sys
import sqlite3
import logging
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("merge_accounts")

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "accounts.yaml"
SCHEMA_PATH = SCRIPT_DIR / "schema.sql"


def init_database(db_path: str):
    """Create database and apply schema if needed."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    logger.info("Database initialized at %s", db_path)
    return conn


def ensure_account_exists(conn: sqlite3.Connection, row: dict):
    """Create Account record if it doesn't exist."""
    existing = conn.execute(
        "SELECT Id FROM Accounts WHERE Mt5Login = ?", (row["account_login"],)
    ).fetchone()
    if existing is None:
        account_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO Accounts (Id, Mt5Login, Server, PrimaryTraderName, AccountType, Status, Currency, CreatedAt)
               VALUES (?, ?, ?, ?, 0, 0, ?, ?)""",
            (account_id, row["account_login"], row.get("account_server", ""),
             row.get("trader", "Unknown"), row.get("account_currency", "USD"),
             datetime.utcnow().isoformat()),
        )
        return account_id
    return existing["Id"]


def merge_trades(new_df: pd.DataFrame, conn: sqlite3.Connection, source: str = "csv") -> dict:
    """
    Merge new trades into SQLite using composite key logic.
    Returns stats dict with counts of new/updated/skipped.
    """
    stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}

    for _, row in new_df.iterrows():
        try:
            account_login = int(row["account_login"])
            ticket = int(row["ticket"])
            deal_exit_ticket = int(row.get("deal_exit_ticket", 0))

            # Look up by composite key
            existing = conn.execute(
                """SELECT Id, IsOpen, ExitPrice FROM Trades
                   WHERE AccountLogin = ? AND Ticket = ? AND DealExitTicket = ?""",
                (account_login, ticket, deal_exit_ticket),
            ).fetchone()

            account_id = ensure_account_exists(conn, row.to_dict())

            if existing is None:
                # NEW -> INSERT
                trade_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO Trades (
                        Id, AccountId, Ticket, DealEntryTicket, DealExitTicket,
                        Symbol, Direction, MagicNumber, TradeOrigin,
                        OrderComment, EntryTime, ExitTime, EntryPrice, ExitPrice,
                        Volume, ProfitLoss, Commission, Swap,
                        Status, IsOpen, Mfe, Mae, HoldingTimeMinutes,
                        AccountLogin, AccountServer, AccountName, AccountCurrency,
                        CategorizationStatus
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, -1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    (
                        trade_id, account_id, ticket,
                        int(row.get("deal_entry_ticket", 0)), deal_exit_ticket,
                        str(row["symbol"]), int(row["direction"]), int(row["magic_number"]),
                        str(row.get("comment", "")),
                        str(row["entry_time"]), row.get("exit_time"),
                        float(row["entry_price"]), float(row.get("exit_price", 0)),
                        float(row["volume"]), float(row.get("profit_loss", 0)),
                        float(row.get("commission", 0)), float(row.get("swap", 0)),
                        0 if row.get("is_open", 1) == 0 else 0,
                        int(row.get("is_open", 1)),
                        row.get("mfe"), row.get("mae"),
                        float(row.get("holding_time_minutes", 0)),
                        account_login, str(row.get("account_server", "")),
                        str(row.get("account_name", "")), str(row.get("account_currency", "USD")),
                    ),
                )
                stats["new"] += 1

            elif existing["IsOpen"] == 1 and float(row.get("exit_price", 0)) > 0:
                # OPEN -> CLOSED -> UPDATE
                conn.execute(
                    """UPDATE Trades SET
                        ExitPrice = ?, ExitTime = ?, ProfitLoss = ?,
                        Commission = ?, Swap = ?, IsOpen = 0, Status = 1,
                        Mfe = ?, Mae = ?, HoldingTimeMinutes = ?
                    WHERE Id = ?""",
                    (
                        float(row["exit_price"]), row.get("exit_time"),
                        float(row.get("profit_loss", 0)),
                        float(row.get("commission", 0)), float(row.get("swap", 0)),
                        row.get("mfe"), row.get("mae"),
                        float(row.get("holding_time_minutes", 0)),
                        existing["Id"],
                    ),
                )
                stats["updated"] += 1

            else:
                # ALREADY CLOSED -> SKIP
                stats["skipped"] += 1

        except Exception as e:
            logger.error("Error merging trade ticket=%s: %s", row.get("ticket"), e)
            stats["errors"] += 1

    conn.commit()
    return stats


def log_sync(conn: sqlite3.Connection, account_login: int, stats: dict, source: str):
    """Record sync event in SyncLog."""
    conn.execute(
        """INSERT INTO SyncLog (AccountLogin, SyncStartedAt, SyncCompletedAt,
           NewTrades, UpdatedTrades, SkippedTrades, Source)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            account_login,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            stats["new"], stats["updated"], stats["skipped"], source,
        ),
    )
    conn.execute(
        "UPDATE Accounts SET LastSyncAt = ? WHERE Mt5Login = ?",
        (datetime.utcnow().isoformat(), account_login),
    )
    conn.commit()


def merge_csv_files(csv_dir: Path, db_path: str):
    """Find all CSV files in directory and merge into database."""
    conn = init_database(db_path)

    csv_files = sorted(csv_dir.glob("trades_*.csv"))
    if not csv_files:
        logger.warning("No CSV files found in %s", csv_dir)
        return

    for csv_file in csv_files:
        logger.info("Merging %s...", csv_file.name)
        df = pd.read_csv(csv_file)
        if df.empty:
            continue

        account_login = df["account_login"].iloc[0] if "account_login" in df.columns else 0
        stats = merge_trades(df, conn, source="csv")
        log_sync(conn, int(account_login), stats, "csv")
        logger.info(
            "Account %s: new=%d, updated=%d, skipped=%d, errors=%d",
            account_login, stats["new"], stats["updated"], stats["skipped"], stats["errors"],
        )

    conn.close()


def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    db_path = cfg.get("database_path", "./data/pnl_dashboard.db")
    export_dir = Path(cfg.get("export_dir", "./data/mt5_exports"))

    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    merge_csv_files(export_dir, db_path)
    logger.info("Merge complete")


if __name__ == "__main__":
    main()
