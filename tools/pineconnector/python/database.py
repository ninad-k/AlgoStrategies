"""Trade storage — SQLite by default, PostgreSQL optional."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

from . import config

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id        TEXT NOT NULL UNIQUE,
    raw_payload      TEXT NOT NULL,
    action           TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    lot              REAL NOT NULL,
    sl               REAL DEFAULT 0,
    tp               REAL DEFAULT 0,
    risk_passed      INTEGER NOT NULL DEFAULT 1,
    rejection_reason TEXT DEFAULT '',
    dry_run          INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id       TEXT NOT NULL,
    ticket          INTEGER DEFAULT 0,
    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL,
    lot             REAL NOT NULL,
    entry_price     REAL DEFAULT 0,
    exit_price      REAL DEFAULT 0,
    sl              REAL DEFAULT 0,
    tp              REAL DEFAULT 0,
    profit          REAL DEFAULT 0,
    commission      REAL DEFAULT 0,
    swap            REAL DEFAULT 0,
    open_time       TEXT NOT NULL,
    close_time      TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    remaining_lot   REAL DEFAULT 0,
    comment         TEXT DEFAULT '',
    magic           INTEGER DEFAULT 0,
    FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
);

CREATE TABLE IF NOT EXISTS partial_closes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id        INTEGER NOT NULL,
    signal_id       TEXT NOT NULL,
    tp_level        INTEGER NOT NULL,
    closed_lot      REAL NOT NULL,
    close_price     REAL NOT NULL,
    profit          REAL DEFAULT 0,
    new_sl          REAL DEFAULT 0,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT NOT NULL UNIQUE,
    total_trades     INTEGER DEFAULT 0,
    winning_trades   INTEGER DEFAULT 0,
    losing_trades    INTEGER DEFAULT 0,
    total_pnl        REAL DEFAULT 0,
    total_commission REAL DEFAULT 0,
    max_drawdown     REAL DEFAULT 0,
    equity_high      REAL DEFAULT 0,
    equity_low       REAL DEFAULT 0,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_open_time ON trades(open_time);
CREATE INDEX IF NOT EXISTS idx_partial_trade ON partial_closes(trade_id);
"""


def get_connection() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
    log.info("Database initialised at %s", config.DB_PATH)


def save_signal(
    signal_id: str,
    raw_payload: str,
    action: str,
    symbol: str,
    lot: float,
    sl: float,
    tp: float,
    risk_passed: bool,
    rejection_reason: str,
    dry_run: bool,
    created_at: str,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO signals
               (signal_id, raw_payload, action, symbol, lot, sl, tp,
                risk_passed, rejection_reason, dry_run, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal_id,
                raw_payload,
                action,
                symbol,
                lot,
                sl,
                tp,
                int(risk_passed),
                rejection_reason,
                int(dry_run),
                created_at,
            ),
        )
        return cur.lastrowid  # type: ignore[return-value]


def save_trade(
    signal_id: str,
    ticket: int,
    symbol: str,
    action: str,
    lot: float,
    entry_price: float,
    sl: float,
    tp: float,
    open_time: str,
    status: str = "pending",
    remaining_lot: float = 0,
    comment: str = "",
    magic: int = 0,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO trades
               (signal_id, ticket, symbol, action, lot, entry_price, sl, tp,
                open_time, status, remaining_lot, comment, magic)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal_id,
                ticket,
                symbol,
                action,
                lot,
                entry_price,
                sl,
                tp,
                open_time,
                status,
                remaining_lot,
                comment,
                magic,
            ),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_trade(
    signal_id: str,
    **fields: Any,
) -> None:
    if not fields:
        return
    allowed = {
        "ticket",
        "entry_price",
        "exit_price",
        "sl",
        "tp",
        "profit",
        "commission",
        "swap",
        "close_time",
        "status",
        "remaining_lot",
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = ?" for k in cols)
    values = list(cols.values()) + [signal_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE trades SET {set_clause} WHERE signal_id = ?",
            values,
        )


def save_partial_close(
    trade_id: int,
    signal_id: str,
    tp_level: int,
    closed_lot: float,
    close_price: float,
    profit: float,
    new_sl: float,
    created_at: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO partial_closes
               (trade_id, signal_id, tp_level, closed_lot, close_price,
                profit, new_sl, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, signal_id, tp_level, closed_lot, close_price, profit, new_sl, created_at),
        )


def get_trades(
    limit: int = 50,
    offset: int = 0,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM trades {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_trade_by_signal(signal_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM trades WHERE signal_id = ?", (signal_id,)
        ).fetchone()
        return dict(row) if row else None


def get_open_trades() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status IN ('pending', 'open', 'partial') ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_daily_trade_count(date_str: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE created_at LIKE ? AND risk_passed = 1",
            (f"{date_str}%",),
        ).fetchone()
        return row["cnt"] if row else 0


def get_daily_pnl(date_str: str) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(profit), 0) as total FROM trades WHERE open_time LIKE ?",
            (f"{date_str}%",),
        ).fetchone()
        return row["total"] if row else 0.0
