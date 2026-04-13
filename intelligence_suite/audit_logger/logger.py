"""
Intelligence Suite — Audit Logger
====================================
Append-only dual-write logger: JSON Lines file + SQLite via SQLAlchemy.
Every trade, AI decision, and risk check is recorded immutably.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence_suite.audit_logger.schema import AuditEntry, create_tables

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Append-only audit logger with dual storage:
    - JSON Lines file for fast streaming / grep
    - SQLite database for structured queries
    """

    def __init__(
        self,
        jsonl_path: str = "logs/audit_log.jsonl",
        db_path: str = "logs/audit_logger.db",
    ):
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._SessionFactory = create_tables(db_path)
        logger.info(
            f"AuditLogger initialized: jsonl={self.jsonl_path}, db={self.db_path}"
        )

    def _write_jsonl(self, record: dict[str, Any]) -> None:
        """Append a single JSON line to the log file."""
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.error(f"Failed to write JSONL: {exc}")

    def _write_db(self, entry: AuditEntry) -> None:
        """Insert an audit entry into SQLite."""
        try:
            session = self._SessionFactory()
            session.add(entry)
            session.commit()
            session.close()
        except Exception as exc:
            logger.error(f"Failed to write to DB: {exc}")

    def log_trade(
        self,
        trade: dict[str, Any],
        ai_reasoning: str = "",
        indicators: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a trade execution event.

        Parameters
        ----------
        trade : dict
            Must include: symbol, action, volume/qty, entry_price, sl, tp.
        ai_reasoning : str
            The AI model's reasoning for the trade.
        indicators : dict
            Snapshot of indicator values at trade time.
        """
        now = datetime.utcnow()
        record = {
            "timestamp": now.isoformat(),
            "event_type": "TRADE",
            "symbol": trade.get("symbol", ""),
            "action": trade.get("action", ""),
            "trade": trade,
            "ai_reasoning": ai_reasoning,
            "indicators": indicators or {},
        }
        self._write_jsonl(record)

        entry = AuditEntry(
            timestamp=now,
            event_type="TRADE",
            symbol=trade.get("symbol"),
            action=trade.get("action"),
            details_json=json.dumps(trade, default=str),
            model_name=trade.get("model_name"),
            confidence=trade.get("confidence"),
            profit=trade.get("profit"),
            ai_reasoning=ai_reasoning,
            indicators_json=json.dumps(indicators, default=str) if indicators else None,
        )
        self._write_db(entry)
        logger.info(
            f"Trade logged: {trade.get('symbol')} {trade.get('action')} "
            f"vol={trade.get('volume', trade.get('qty'))}"
        )

    def log_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        model_name: str,
        reason: str,
    ) -> None:
        """
        Log an AI model decision (before execution).

        Parameters
        ----------
        symbol : str
            Trading symbol.
        action : str
            BUY / SELL / HOLD.
        confidence : float
            Model confidence (0-1).
        model_name : str
            Name of the model that made the decision.
        reason : str
            Human-readable explanation.
        """
        now = datetime.utcnow()
        record = {
            "timestamp": now.isoformat(),
            "event_type": "DECISION",
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "model_name": model_name,
            "reason": reason,
        }
        self._write_jsonl(record)

        entry = AuditEntry(
            timestamp=now,
            event_type="DECISION",
            symbol=symbol,
            action=action,
            model_name=model_name,
            confidence=confidence,
            ai_reasoning=reason,
        )
        self._write_db(entry)
        logger.debug(
            f"Decision logged: {symbol} {action} conf={confidence:.2f} by {model_name}"
        )

    def log_risk_check(
        self,
        symbol: str,
        allowed: bool,
        reason: str,
    ) -> None:
        """
        Log a risk management check result.

        Parameters
        ----------
        symbol : str
            Symbol being checked.
        allowed : bool
            Whether the trade was allowed.
        reason : str
            Explanation of the risk check outcome.
        """
        now = datetime.utcnow()
        record = {
            "timestamp": now.isoformat(),
            "event_type": "RISK_CHECK",
            "symbol": symbol,
            "allowed": allowed,
            "reason": reason,
        }
        self._write_jsonl(record)

        entry = AuditEntry(
            timestamp=now,
            event_type="RISK_CHECK",
            symbol=symbol,
            risk_allowed=str(allowed),
            risk_reason=reason,
        )
        self._write_db(entry)
        logger.debug(f"Risk check logged: {symbol} allowed={allowed}")

    def get_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Retrieve recent audit entries from SQLite.

        Parameters
        ----------
        limit : int
            Maximum number of entries to return.

        Returns
        -------
        list of dict representations of AuditEntry rows.
        """
        try:
            session = self._SessionFactory()
            entries = (
                session.query(AuditEntry)
                .order_by(AuditEntry.timestamp.desc())
                .limit(limit)
                .all()
            )
            result = []
            for e in entries:
                result.append({
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "event_type": e.event_type,
                    "symbol": e.symbol,
                    "action": e.action,
                    "details_json": e.details_json,
                    "model_name": e.model_name,
                    "confidence": e.confidence,
                    "profit": e.profit,
                    "ai_reasoning": e.ai_reasoning,
                    "risk_allowed": e.risk_allowed,
                    "risk_reason": e.risk_reason,
                })
            session.close()
            return result
        except Exception as exc:
            logger.error(f"Failed to read audit log: {exc}")
            return []
