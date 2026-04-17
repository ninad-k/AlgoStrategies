"""SQLite persistence for backtest sessions, trades, and metrics."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "backtester.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS backtests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL DEFAULT '',
                symbol          TEXT NOT NULL,
                timeframe       TEXT NOT NULL,
                start_date      TEXT NOT NULL,
                end_date        TEXT NOT NULL,
                initial_capital REAL NOT NULL DEFAULT 10000,
                leverage        REAL NOT NULL DEFAULT 1,
                commission_pct  REAL NOT NULL DEFAULT 0,
                slippage_points REAL NOT NULL DEFAULT 0,
                strategy_source TEXT DEFAULT '',
                strategy_name   TEXT DEFAULT '',
                strategy_config TEXT DEFAULT '{}',
                input_overrides TEXT DEFAULT '{}',
                status          TEXT NOT NULL DEFAULT 'pending',
                progress        REAL DEFAULT 0,
                phase           TEXT DEFAULT '',
                error           TEXT,
                created_at      TEXT NOT NULL,
                completed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS trades (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id     INTEGER NOT NULL,
                order_num       INTEGER,
                deal_num        INTEGER,
                open_time       TEXT,
                close_time      TEXT,
                symbol          TEXT,
                type            TEXT,
                direction       TEXT,
                volume          REAL,
                entry_price     REAL,
                exit_price      REAL,
                sl              REAL DEFAULT 0,
                tp              REAL DEFAULT 0,
                commission      REAL DEFAULT 0,
                swap            REAL DEFAULT 0,
                profit          REAL DEFAULT 0,
                balance         REAL DEFAULT 0,
                comment         TEXT DEFAULT '',
                mfe             REAL DEFAULT 0,
                mae             REAL DEFAULT 0,
                FOREIGN KEY (backtest_id) REFERENCES backtests(id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id     INTEGER NOT NULL,
                open_time       TEXT,
                order_num       INTEGER,
                symbol          TEXT,
                type            TEXT,
                volume          TEXT,
                price           REAL,
                sl              REAL DEFAULT 0,
                tp              REAL DEFAULT 0,
                time            TEXT DEFAULT '',
                state           TEXT DEFAULT 'filled',
                comment         TEXT DEFAULT '',
                FOREIGN KEY (backtest_id) REFERENCES backtests(id)
            );

            CREATE TABLE IF NOT EXISTS deals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id     INTEGER NOT NULL,
                time            TEXT,
                deal_num        INTEGER,
                symbol          TEXT,
                type            TEXT,
                direction       TEXT,
                volume          REAL,
                price           REAL,
                order_num       INTEGER,
                commission      REAL DEFAULT 0,
                swap            REAL DEFAULT 0,
                profit          REAL DEFAULT 0,
                balance         REAL DEFAULT 0,
                comment         TEXT DEFAULT '',
                FOREIGN KEY (backtest_id) REFERENCES backtests(id)
            );

            CREATE TABLE IF NOT EXISTS equity_curve (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id     INTEGER NOT NULL,
                timestamp       TEXT NOT NULL,
                balance         REAL NOT NULL,
                equity          REAL NOT NULL,
                drawdown        REAL DEFAULT 0,
                drawdown_pct    REAL DEFAULT 0,
                FOREIGN KEY (backtest_id) REFERENCES backtests(id)
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id     INTEGER NOT NULL UNIQUE,
                data            TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (backtest_id) REFERENCES backtests(id)
            );

            CREATE INDEX IF NOT EXISTS idx_trades_backtest ON trades(backtest_id);
            CREATE INDEX IF NOT EXISTS idx_orders_backtest ON orders(backtest_id);
            CREATE INDEX IF NOT EXISTS idx_deals_backtest ON deals(backtest_id);
            CREATE INDEX IF NOT EXISTS idx_equity_backtest ON equity_curve(backtest_id);
        """)


def create_backtest(data: dict) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO backtests
               (name, symbol, timeframe, start_date, end_date, initial_capital,
                leverage, commission_pct, slippage_points, strategy_source,
                strategy_name, strategy_config, input_overrides, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("name", ""),
                data["symbol"],
                data["timeframe"],
                data["start_date"],
                data["end_date"],
                data.get("initial_capital", 10000),
                data.get("leverage", 1),
                data.get("commission_pct", 0),
                data.get("slippage_points", 0),
                data.get("strategy_source", ""),
                data.get("strategy_name", ""),
                json.dumps(data.get("strategy_config", {})),
                json.dumps(data.get("input_overrides", {})),
                "pending",
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def update_backtest_status(bt_id: int, status: str, progress: float = 0,
                           phase: str = "", error: Optional[str] = None):
    with get_connection() as conn:
        if status == "complete":
            conn.execute(
                """UPDATE backtests SET status=?, progress=?, phase=?, error=?,
                   completed_at=? WHERE id=?""",
                (status, progress, phase, error, datetime.utcnow().isoformat(), bt_id),
            )
        else:
            conn.execute(
                "UPDATE backtests SET status=?, progress=?, phase=?, error=? WHERE id=?",
                (status, progress, phase, error, bt_id),
            )


def get_backtest(bt_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM backtests WHERE id=?", (bt_id,)).fetchone()
        return dict(row) if row else None


def get_all_backtests() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM backtests ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def save_trades(bt_id: int, trades: list[dict]):
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO trades
               (backtest_id, order_num, deal_num, open_time, close_time, symbol,
                type, direction, volume, entry_price, exit_price, sl, tp,
                commission, swap, profit, balance, comment, mfe, mae)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (bt_id, t.get("order_num", 0), t.get("deal_num", 0),
                 t.get("open_time", ""), t.get("close_time", ""),
                 t.get("symbol", ""), t.get("type", ""), t.get("direction", ""),
                 t.get("volume", 0), t.get("entry_price", 0), t.get("exit_price", 0),
                 t.get("sl", 0), t.get("tp", 0), t.get("commission", 0),
                 t.get("swap", 0), t.get("profit", 0), t.get("balance", 0),
                 t.get("comment", ""), t.get("mfe", 0), t.get("mae", 0))
                for t in trades
            ],
        )


def save_orders(bt_id: int, orders: list[dict]):
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO orders
               (backtest_id, open_time, order_num, symbol, type, volume,
                price, sl, tp, time, state, comment)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (bt_id, o.get("open_time", ""), o.get("order_num", 0),
                 o.get("symbol", ""), o.get("type", ""), o.get("volume", ""),
                 o.get("price", 0), o.get("sl", 0), o.get("tp", 0),
                 o.get("time", ""), o.get("state", "filled"), o.get("comment", ""))
                for o in orders
            ],
        )


def save_deals(bt_id: int, deals: list[dict]):
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO deals
               (backtest_id, time, deal_num, symbol, type, direction, volume,
                price, order_num, commission, swap, profit, balance, comment)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (bt_id, d.get("time", ""), d.get("deal_num", 0),
                 d.get("symbol", ""), d.get("type", ""), d.get("direction", ""),
                 d.get("volume", 0), d.get("price", 0), d.get("order_num", 0),
                 d.get("commission", 0), d.get("swap", 0), d.get("profit", 0),
                 d.get("balance", 0), d.get("comment", ""))
                for d in deals
            ],
        )


def save_equity_curve(bt_id: int, points: list[dict]):
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO equity_curve
               (backtest_id, timestamp, balance, equity, drawdown, drawdown_pct)
               VALUES (?,?,?,?,?,?)""",
            [
                (bt_id, p["timestamp"], p["balance"], p["equity"],
                 p.get("drawdown", 0), p.get("drawdown_pct", 0))
                for p in points
            ],
        )


def save_metrics(bt_id: int, data: dict):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metrics (backtest_id, data) VALUES (?, ?)",
            (bt_id, json.dumps(data)),
        )


def get_trades(bt_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE backtest_id=? ORDER BY id", (bt_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_orders(bt_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE backtest_id=? ORDER BY id", (bt_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_deals(bt_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM deals WHERE backtest_id=? ORDER BY id", (bt_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_equity_curve(bt_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM equity_curve WHERE backtest_id=? ORDER BY timestamp",
            (bt_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_metrics(bt_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT data FROM metrics WHERE backtest_id=?", (bt_id,)
        ).fetchone()
        return json.loads(row["data"]) if row else {}


def delete_backtest(bt_id: int):
    with get_connection() as conn:
        for tbl in ("trades", "orders", "deals", "equity_curve", "metrics"):
            conn.execute(f"DELETE FROM {tbl} WHERE backtest_id=?", (bt_id,))
        conn.execute("DELETE FROM backtests WHERE id=?", (bt_id,))
