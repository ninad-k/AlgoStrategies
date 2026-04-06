"""
Trade Classification Script
Applies manual/automated/semi-manual classification to trades in SQLite.
Uses magic_mapping.yaml for strategy assignment and comment pattern matching.
"""
import os
import sys
import sqlite3
import logging
from enum import IntEnum
from pathlib import Path

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("classify_trades")

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "accounts.yaml"
DEFAULT_MAPPING = SCRIPT_DIR / "magic_mapping.yaml"


class TradeOrigin(IntEnum):
    UNCLASSIFIED = -1
    MANUAL = 0
    AUTOMATED = 1
    SEMI_MANUAL = 2


def load_magic_mapping(path: Path = DEFAULT_MAPPING) -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    strategies = {}
    for magic, name in cfg.get("strategies", {}).items():
        strategies[int(magic)] = str(name)
    comment_patterns = []
    for entry in cfg.get("comment_patterns", {}).get("semi_manual", []):
        comment_patterns.append(entry["pattern"].lower())
    return {"strategies": strategies, "comment_patterns": comment_patterns}


def classify_trade(magic_number: int, comment: str, mapping: dict) -> tuple:
    """
    Classify a single trade.
    Returns (TradeOrigin, strategy_name or None).
    """
    if magic_number > 0:
        strategy = mapping["strategies"].get(
            magic_number, f"Unknown_EA_{magic_number}"
        )
        return (TradeOrigin.AUTOMATED, strategy)

    comment_lower = (comment or "").lower()
    for pattern in mapping["comment_patterns"]:
        if pattern in comment_lower:
            return (TradeOrigin.SEMI_MANUAL, None)

    return (TradeOrigin.MANUAL, None)


def classify_all_unclassified(db_path: str, mapping: dict) -> dict:
    """Classify all trades with TradeOrigin = -1 (Unclassified)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    unclassified = conn.execute(
        "SELECT Id, MagicNumber, OrderComment FROM Trades WHERE TradeOrigin = -1"
    ).fetchall()

    stats = {"manual": 0, "automated": 0, "semi_manual": 0, "total": len(unclassified)}
    logger.info("Found %d unclassified trades", len(unclassified))

    for trade in unclassified:
        origin, strategy = classify_trade(
            trade["MagicNumber"], trade["OrderComment"], mapping
        )

        conn.execute(
            """UPDATE Trades SET TradeOrigin = ?, StrategyName = ?,
               CategorizationStatus = 1
               WHERE Id = ?""",
            (int(origin), strategy, trade["Id"]),
        )

        if origin == TradeOrigin.MANUAL:
            stats["manual"] += 1
        elif origin == TradeOrigin.AUTOMATED:
            stats["automated"] += 1
        elif origin == TradeOrigin.SEMI_MANUAL:
            stats["semi_manual"] += 1

    conn.commit()

    # Auto-create Strategy records for newly discovered strategies
    auto_create_strategies(conn, mapping)

    conn.close()
    return stats


def auto_create_strategies(conn: sqlite3.Connection, mapping: dict):
    """Create Strategy records for any strategies found in trades but not yet in Strategies table."""
    distinct = conn.execute(
        "SELECT DISTINCT StrategyName FROM Trades WHERE TradeOrigin = 1 AND StrategyName IS NOT NULL"
    ).fetchall()

    for row in distinct:
        name = row[0]
        existing = conn.execute(
            "SELECT Id FROM Strategies WHERE Name = ?", (name,)
        ).fetchone()
        if existing is None:
            import uuid
            # Find magic numbers for this strategy
            magic_numbers = []
            for magic, sname in mapping["strategies"].items():
                if sname == name:
                    magic_numbers.append(magic)

            conn.execute(
                """INSERT INTO Strategies (Id, Name, MagicNumbers, IsAutoDetected, CreatedAt)
                   VALUES (?, ?, ?, 1, ?)""",
                (
                    str(uuid.uuid4()), name,
                    str(magic_numbers) if magic_numbers else "[]",
                    __import__("datetime").datetime.utcnow().isoformat(),
                ),
            )
            logger.info("Auto-created strategy: %s (magic=%s)", name, magic_numbers)

    conn.commit()


def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    mapping_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAPPING

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    db_path = cfg.get("database_path", "./data/pnl_dashboard.db")
    mapping = load_magic_mapping(mapping_path)

    logger.info("Strategy mapping: %s", mapping["strategies"])
    logger.info("Semi-manual patterns: %s", mapping["comment_patterns"])

    stats = classify_all_unclassified(db_path, mapping)
    logger.info(
        "Classification complete: %d manual, %d automated, %d semi-manual (of %d total)",
        stats["manual"], stats["automated"], stats["semi_manual"], stats["total"],
    )


if __name__ == "__main__":
    main()
