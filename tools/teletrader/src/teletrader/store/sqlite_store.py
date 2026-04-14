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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    lots REAL DEFAULT 0,
                    price REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,
                    source TEXT DEFAULT 'unknown',
                    details TEXT DEFAULT '',
                    created_at TEXT NOT NULL
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

    # --- Trade event methods ---

    def add_trade_event(
        self,
        signal_id: str,
        event_type: str,
        symbol: str,
        direction: str,
        lots: float = 0,
        price: float = 0,
        pnl: float = 0,
        source: str = "unknown",
        details: str = "",
    ) -> int:
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """INSERT INTO trade_events
                       (signal_id, event_type, symbol, direction, lots, price,
                        pnl, source, details, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        signal_id, event_type, symbol, direction,
                        lots, price, pnl, source, details,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                return cursor.lastrowid  # type: ignore[return-value]

    def get_trade_events(
        self,
        signal_id: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        conditions: list[str] = []
        params: list = []
        if signal_id:
            conditions.append("signal_id = ?")
            params.append(signal_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM trade_events{where} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_performance_by_source(self) -> list[dict]:
        """Win rate and P&L grouped by signal source (channel)."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    te.source,
                    COUNT(DISTINCT te.signal_id) as total_trades,
                    SUM(CASE WHEN te.event_type = 'closed' AND te.pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN te.event_type = 'closed' AND te.pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN te.event_type = 'closed' THEN te.pnl ELSE 0 END) as total_pnl,
                    SUM(CASE WHEN te.event_type = 'tp1_hit' THEN 1 ELSE 0 END) as tp1_hits,
                    SUM(CASE WHEN te.event_type = 'tp2_hit' THEN 1 ELSE 0 END) as tp2_hits,
                    SUM(CASE WHEN te.event_type = 'tp3_hit' THEN 1 ELSE 0 END) as tp3_hits
                FROM trade_events te
                GROUP BY te.source
                ORDER BY total_pnl DESC
            """).fetchall()
            result = []
            for row in rows:
                total_closed = row["wins"] + row["losses"]
                win_rate = (row["wins"] / total_closed * 100) if total_closed > 0 else 0
                result.append({
                    "source": row["source"],
                    "total_trades": row["total_trades"],
                    "wins": row["wins"],
                    "losses": row["losses"],
                    "win_rate": round(win_rate, 1),
                    "total_pnl": round(row["total_pnl"], 2),
                    "tp1_hits": row["tp1_hits"],
                    "tp2_hits": row["tp2_hits"],
                    "tp3_hits": row["tp3_hits"],
                })
            return result

    def get_performance_by_symbol(self) -> list[dict]:
        """Win rate and P&L grouped by symbol."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    symbol,
                    COUNT(DISTINCT signal_id) as total_trades,
                    SUM(CASE WHEN event_type = 'closed' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN event_type = 'closed' AND pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN event_type = 'closed' THEN pnl ELSE 0 END) as total_pnl
                FROM trade_events
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """).fetchall()
            result = []
            for row in rows:
                total_closed = row["wins"] + row["losses"]
                win_rate = (row["wins"] / total_closed * 100) if total_closed > 0 else 0
                result.append({
                    "symbol": row["symbol"],
                    "total_trades": row["total_trades"],
                    "wins": row["wins"],
                    "losses": row["losses"],
                    "win_rate": round(win_rate, 1),
                    "total_pnl": round(row["total_pnl"], 2),
                })
            return result

    def get_daily_pnl(self, days: int = 30) -> list[dict]:
        """Daily P&L from closed trades."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DATE(created_at) as day,
                          SUM(pnl) as daily_pnl,
                          COUNT(*) as trades
                   FROM trade_events
                   WHERE event_type = 'closed'
                     AND created_at >= DATE('now', ?)
                   GROUP BY day ORDER BY day ASC""",
                (f"-{days} days",),
            ).fetchall()
            return [{"date": row["day"], "pnl": round(row["daily_pnl"], 2),
                     "trades": row["trades"]} for row in rows]

    def get_overall_performance(self) -> dict:
        """Overall P&L and win/loss stats."""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_closed,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM trade_events
                WHERE event_type = 'closed'
            """).fetchone()

            total_closed = row["total_closed"] or 0
            wins = row["wins"] or 0
            losses = row["losses"] or 0
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

            # Count active signals and events
            total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            total_events = conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0]
            placed = conn.execute(
                "SELECT COUNT(*) FROM trade_events WHERE event_type = 'order_placed'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM trade_events WHERE event_type = 'order_failed'"
            ).fetchone()[0]
            symbol_not_found = conn.execute(
                "SELECT COUNT(*) FROM trade_events WHERE event_type = 'symbol_not_found'"
            ).fetchone()[0]

            return {
                "total_signals": total_signals,
                "total_events": total_events,
                "orders_placed": placed,
                "orders_failed": failed,
                "symbol_not_found": symbol_not_found,
                "total_closed": total_closed,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 1),
                "total_pnl": round(row["total_pnl"] or 0, 2),
                "avg_pnl": round(row["avg_pnl"] or 0, 2),
                "best_trade": round(row["best_trade"] or 0, 2),
                "worst_trade": round(row["worst_trade"] or 0, 2),
            }
