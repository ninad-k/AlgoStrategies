"""SQLite-backed signal store with persistent storage and dashboard queries."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime

from teletrader.models.trading_signal import TradingSignal


class SQLiteSignalStore:
    """Persistent signal store using SQLite.

    Thread-safe via threading.Lock. Uses WAL mode for concurrent read access.
    """

    def __init__(self, db_path: str = "teletrader.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profits TEXT NOT NULL,
                    lot_size REAL,
                    raw_text TEXT NOT NULL,
                    source TEXT DEFAULT 'unknown',
                    parsed_at_utc TEXT NOT NULL,
                    received_at_utc TEXT NOT NULL
                )
            """)

    def _row_to_signal(self, row: sqlite3.Row) -> TradingSignal:
        return TradingSignal(
            signal_id=row["signal_id"],
            seq=row["seq"],
            symbol=row["symbol"],
            direction=row["direction"],
            order_type=row["order_type"],
            entry_price=row["entry_price"],
            stop_loss=row["stop_loss"],
            take_profits=json.loads(row["take_profits"]),
            lot_size=row["lot_size"],
            raw_text=row["raw_text"],
            source=row["source"] or "unknown",
            parsed_at_utc=datetime.fromisoformat(row["parsed_at_utc"]),
            received_at_utc=datetime.fromisoformat(row["received_at_utc"]),
        )

    # --- SignalStoreProtocol methods ---

    def append(self, signal: TradingSignal) -> TradingSignal:
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """INSERT INTO signals
                       (signal_id, symbol, direction, order_type, entry_price,
                        stop_loss, take_profits, lot_size, raw_text, source,
                        parsed_at_utc, received_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        signal.signal_id,
                        signal.symbol,
                        signal.direction,
                        signal.order_type,
                        signal.entry_price,
                        signal.stop_loss,
                        json.dumps(signal.take_profits),
                        signal.lot_size,
                        signal.raw_text,
                        signal.source,
                        signal.parsed_at_utc.isoformat(),
                        signal.received_at_utc.isoformat(),
                    ),
                )
                signal.seq = cursor.lastrowid  # type: ignore[assignment]
                return signal

    def since(self, seq: int) -> list[TradingSignal]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM signals WHERE seq > ? ORDER BY seq ASC", (seq,)
            ).fetchall()
            return [self._row_to_signal(row) for row in rows]

    def get(self, signal_id: str) -> TradingSignal | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?", (signal_id,)
            ).fetchone()
            return self._row_to_signal(row) if row else None

    # --- Dashboard query methods ---

    def list_signals(
        self,
        source: str | None = None,
        symbol: str | None = None,
        from_dt: str | None = None,
        to_dt: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TradingSignal]:
        conditions: list[str] = []
        params: list = []

        if source:
            conditions.append("source LIKE ?")
            params.append(f"%{source}%")
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if from_dt:
            conditions.append("parsed_at_utc >= ?")
            params.append(from_dt)
        if to_dt:
            conditions.append("parsed_at_utc <= ?")
            params.append(to_dt)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM signals{where} ORDER BY seq DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_signal(row) for row in rows]

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

            by_source = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) as cnt FROM signals GROUP BY source ORDER BY cnt DESC"
            ).fetchall():
                by_source[row["source"]] = row["cnt"]

            by_symbol = {}
            for row in conn.execute(
                "SELECT symbol, COUNT(*) as cnt FROM signals GROUP BY symbol ORDER BY cnt DESC"
            ).fetchall():
                by_symbol[row["symbol"]] = row["cnt"]

            return {
                "total_signals": total,
                "by_source": by_source,
                "by_symbol": by_symbol,
            }

    def get_daily_counts(self, days: int = 30) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DATE(parsed_at_utc) as day, COUNT(*) as cnt
                   FROM signals
                   WHERE parsed_at_utc >= DATE('now', ?)
                   GROUP BY day ORDER BY day ASC""",
                (f"-{days} days",),
            ).fetchall()
            return [{"date": row["day"], "count": row["cnt"]} for row in rows]

    def count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
