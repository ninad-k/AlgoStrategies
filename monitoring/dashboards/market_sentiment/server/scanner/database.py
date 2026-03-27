"""SQLite persistence for stock scanner sessions and scores."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Store DB alongside market_sentiment data directory
DB_PATH = Path(__file__).parent.parent.parent / "data" / "scanner.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scan_sessions (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at        TEXT NOT NULL,
                completed_at      TEXT,
                status            TEXT NOT NULL DEFAULT 'running',
                phase             TEXT DEFAULT '',
                total_symbols     INTEGER DEFAULT 0,
                processed_symbols INTEGER DEFAULT 0,
                error             TEXT
            );

            CREATE TABLE IF NOT EXISTS stock_scores (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id          INTEGER NOT NULL,
                symbol              TEXT NOT NULL,
                company_name        TEXT,
                sector              TEXT,
                industry            TEXT,
                market_cap          REAL,
                price               REAL,
                price_change_pct    REAL,
                avg_volume          REAL,
                rsi                 REAL,
                stage               INTEGER,
                rs_vs_spy           REAL,
                volume_ratio        REAL,
                revenue_growth      REAL,
                gross_margin        REAL,
                debt_equity         REAL,
                eps_trend           TEXT,
                multibagger_score   REAL DEFAULT 0,
                investment_score    REAL DEFAULT 0,
                swing_medium_score  REAL DEFAULT 0,
                swing_short_score   REAL DEFAULT 0,
                red_flags           TEXT DEFAULT '[]',
                score_breakdown     TEXT DEFAULT '{}',
                ai_insight          TEXT DEFAULT NULL,
                scanned_at          TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES scan_sessions(id),
                UNIQUE(session_id, symbol)
            );

            CREATE INDEX IF NOT EXISTS idx_scores_session      ON stock_scores(session_id);
            CREATE INDEX IF NOT EXISTS idx_scores_multibagger  ON stock_scores(session_id, multibagger_score DESC);
            CREATE INDEX IF NOT EXISTS idx_scores_investment   ON stock_scores(session_id, investment_score DESC);
            CREATE INDEX IF NOT EXISTS idx_scores_swing_medium ON stock_scores(session_id, swing_medium_score DESC);
            CREATE INDEX IF NOT EXISTS idx_scores_swing_short  ON stock_scores(session_id, swing_short_score DESC);
        """)


def create_session() -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO scan_sessions (started_at, status) VALUES (?, 'running')",
            (datetime.utcnow().isoformat(),),
        )
        return cur.lastrowid


def update_session(session_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [session_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE scan_sessions SET {fields} WHERE id = ?", values)


def upsert_stock(session_id: int, data: dict):
    data = dict(data)
    data["session_id"] = session_id
    data["scanned_at"] = datetime.utcnow().isoformat()
    if isinstance(data.get("red_flags"), list):
        data["red_flags"] = json.dumps(data["red_flags"])
    if isinstance(data.get("score_breakdown"), dict):
        data["score_breakdown"] = json.dumps(data["score_breakdown"])

    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    updates = ", ".join(
        f"{k} = excluded.{k}" for k in data if k not in ("session_id", "symbol")
    )
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO stock_scores ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(session_id, symbol) DO UPDATE SET {updates}",
            list(data.values()),
        )


def update_ai_insight(session_id: int, symbol: str, insight: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE stock_scores SET ai_insight = ? WHERE session_id = ? AND symbol = ?",
            (insight, session_id, symbol),
        )


def get_latest_session() -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scan_sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_results(
    session_id: int,
    category: str,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = None,
    min_score: float = 0,
    sector: str = None,
    min_market_cap: float = None,
    max_market_cap: float = None,
) -> dict:
    score_col = {
        "multibagger":  "multibagger_score",
        "investment":   "investment_score",
        "swing_medium": "swing_medium_score",
        "swing_short":  "swing_short_score",
    }.get(category, "multibagger_score")

    safe_sort_cols = {
        "symbol", "price", "price_change_pct", "market_cap", "rsi",
        "revenue_growth", "gross_margin", "rs_vs_spy", "volume_ratio",
        "multibagger_score", "investment_score", "swing_medium_score", "swing_short_score",
    }
    sort_col = sort_by if sort_by in safe_sort_cols else score_col

    conditions = [f"session_id = ?", f"{score_col} >= ?"]
    params: list = [session_id, min_score]

    if sector and sector.lower() not in ("", "all"):
        conditions.append("sector = ?")
        params.append(sector)
    if min_market_cap is not None:
        conditions.append("market_cap >= ?")
        params.append(min_market_cap)
    if max_market_cap is not None:
        conditions.append("market_cap <= ?")
        params.append(max_market_cap)

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM stock_scores WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM stock_scores WHERE {where} "
            f"ORDER BY {sort_col} DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "results": [dict(r) for r in rows],
    }


def get_sectors(session_id: int) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT sector FROM stock_scores "
            "WHERE session_id = ? AND sector IS NOT NULL ORDER BY sector",
            (session_id,),
        ).fetchall()
    return [r[0] for r in rows]
