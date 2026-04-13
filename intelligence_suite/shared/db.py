"""
ReySentinel — SQLite Helper
=====================================
Shared database utilities for audit logs, backtest results, etc.
"""

import sqlite3
import json
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "logs/reysentinel.db"


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_tables()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_tables(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    action TEXT,
                    details TEXT,
                    model_name TEXT,
                    confidence REAL,
                    profit REAL
                );

                CREATE TABLE IF NOT EXISTS ensemble_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    final_action TEXT,
                    final_confidence REAL,
                    individual_votes TEXT,
                    regime TEXT,
                    sentiment_score REAL,
                    reason TEXT
                );

                CREATE TABLE IF NOT EXISTS trade_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT,
                    action TEXT,
                    entry_price REAL,
                    close_price REAL,
                    profit REAL,
                    result TEXT,
                    model_name TEXT,
                    regime TEXT,
                    entry_time TEXT,
                    close_time TEXT,
                    duration_minutes REAL
                );

                CREATE TABLE IF NOT EXISTS regime_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    features TEXT
                );

                CREATE TABLE IF NOT EXISTS correlation_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    correlation REAL,
                    lag_minutes INTEGER,
                    method TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_outcomes_symbol ON trade_outcomes(symbol);
                CREATE INDEX IF NOT EXISTS idx_regime_ts ON regime_history(timestamp);
            """)

    def log_audit(self, event_type: str, symbol: str = None, action: str = None,
                  details: dict = None, model_name: str = None,
                  confidence: float = None, profit: float = None):
        from datetime import datetime
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (timestamp, event_type, symbol, action, details, model_name, confidence, profit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), event_type, symbol, action,
                 json.dumps(details) if details else None,
                 model_name, confidence, profit),
            )

    def log_ensemble_decision(self, decision: dict):
        from datetime import datetime
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO ensemble_decisions (timestamp, symbol, final_action, final_confidence, individual_votes, regime, sentiment_score, reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), decision.get("symbol"),
                 decision.get("final_action"), decision.get("final_confidence"),
                 json.dumps(decision.get("individual_decisions", [])),
                 decision.get("regime"), decision.get("sentiment_score"),
                 decision.get("reason")),
            )

    def log_trade_outcome(self, outcome: dict):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO trade_outcomes "
                "(trade_id, symbol, action, entry_price, close_price, profit, result, model_name, regime, entry_time, close_time, duration_minutes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (outcome.get("trade_id"), outcome.get("symbol"), outcome.get("action"),
                 outcome.get("entry_price"), outcome.get("close_price"),
                 outcome.get("profit"), outcome.get("result"),
                 outcome.get("model_name"), outcome.get("regime"),
                 outcome.get("entry_time"), outcome.get("close_time"),
                 outcome.get("duration_minutes")),
            )

    def log_regime(self, symbol: str, regime: str, features: dict = None):
        from datetime import datetime
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO regime_history (timestamp, symbol, regime, features) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), symbol, regime,
                 json.dumps(features) if features else None),
            )

    def get_recent_outcomes(self, limit: int = 100) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trade_outcomes ORDER BY close_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_audit_log(self, limit: int = 200) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
