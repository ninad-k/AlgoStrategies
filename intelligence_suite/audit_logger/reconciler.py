"""
ReySentinel — Trade Reconciler
========================================
Compares backtest expected trades with live executed trades to detect
drift, slippage, and execution quality issues.
"""

import json
import logging
from datetime import datetime
from typing import Any

from intelligence_suite.audit_logger.schema import ReconciliationResult, create_tables

logger = logging.getLogger(__name__)


class TradeReconciler:
    """Reconciles backtest-expected trades against live-executed trades."""

    def __init__(self, db_path: str = "logs/audit_logger.db"):
        self.db_path = db_path
        self._SessionFactory = create_tables(db_path)

    def reconcile(
        self,
        backtest_trades: list[dict[str, Any]],
        live_trades: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compare backtest expected P&L vs live actual P&L.

        Parameters
        ----------
        backtest_trades : list[dict]
            Each dict should have: trade_id or symbol+timestamp, action, pnl, entry_price, exit_price.
        live_trades : list[dict]
            Same structure as backtest_trades.

        Returns
        -------
        dict with: match_rate, pnl_deviation, total_backtest_pnl,
                   total_live_pnl, per_trade_comparison, unmatched_backtest,
                   unmatched_live.
        """
        # Build lookup maps by trade_id or (symbol, action) as fallback
        bt_map: dict[str, dict] = {}
        for t in backtest_trades:
            key = self._trade_key(t)
            bt_map[key] = t

        live_map: dict[str, dict] = {}
        for t in live_trades:
            key = self._trade_key(t)
            live_map[key] = t

        # Match trades
        matched: list[dict] = []
        unmatched_bt: list[dict] = []
        unmatched_live: list[dict] = []

        bt_keys = set(bt_map.keys())
        live_keys = set(live_map.keys())
        common_keys = bt_keys & live_keys

        for key in common_keys:
            bt = bt_map[key]
            live = live_map[key]
            bt_pnl = float(bt.get("pnl", bt.get("profit", 0)))
            live_pnl = float(live.get("pnl", live.get("profit", 0)))
            deviation = live_pnl - bt_pnl

            matched.append({
                "trade_key": key,
                "symbol": bt.get("symbol", live.get("symbol", "")),
                "action": bt.get("action", live.get("action", "")),
                "backtest_pnl": round(bt_pnl, 4),
                "live_pnl": round(live_pnl, 4),
                "deviation": round(deviation, 4),
                "deviation_pct": round(
                    (deviation / abs(bt_pnl) * 100) if bt_pnl != 0 else 0, 2
                ),
                "backtest_entry": bt.get("entry_price"),
                "live_entry": live.get("entry_price"),
                "backtest_exit": bt.get("exit_price"),
                "live_exit": live.get("exit_price"),
            })

        for key in bt_keys - live_keys:
            unmatched_bt.append(bt_map[key])

        for key in live_keys - bt_keys:
            unmatched_live.append(live_map[key])

        # Aggregates
        total_bt_pnl = sum(float(t.get("pnl", t.get("profit", 0))) for t in backtest_trades)
        total_live_pnl = sum(float(t.get("pnl", t.get("profit", 0))) for t in live_trades)
        pnl_deviation = total_live_pnl - total_bt_pnl

        total_possible = max(len(backtest_trades), len(live_trades), 1)
        match_rate = len(matched) / total_possible

        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "match_rate": round(match_rate, 4),
            "pnl_deviation": round(pnl_deviation, 4),
            "total_backtest_pnl": round(total_bt_pnl, 4),
            "total_live_pnl": round(total_live_pnl, 4),
            "matched_count": len(matched),
            "unmatched_backtest_count": len(unmatched_bt),
            "unmatched_live_count": len(unmatched_live),
            "per_trade_comparison": matched,
            "unmatched_backtest": unmatched_bt,
            "unmatched_live": unmatched_live,
        }

        # Persist to database
        self._save_result(result)

        logger.info(
            f"Reconciliation complete: match_rate={match_rate:.2%}, "
            f"pnl_deviation={pnl_deviation:.2f}, "
            f"matched={len(matched)}, unmatched_bt={len(unmatched_bt)}, "
            f"unmatched_live={len(unmatched_live)}"
        )
        return result

    def _trade_key(self, trade: dict) -> str:
        """Generate a unique key for matching trades."""
        trade_id = trade.get("trade_id")
        if trade_id:
            return str(trade_id)
        # Fallback: composite key
        symbol = trade.get("symbol", "")
        action = trade.get("action", "")
        ts = trade.get("timestamp", trade.get("entry_time", ""))
        return f"{symbol}_{action}_{ts}"

    def _save_result(self, result: dict) -> None:
        """Persist reconciliation result to SQLite."""
        try:
            session = self._SessionFactory()
            rec = ReconciliationResult(
                timestamp=datetime.utcnow(),
                backtest_pnl=result["total_backtest_pnl"],
                live_pnl=result["total_live_pnl"],
                deviation=result["pnl_deviation"],
                match_rate=result["match_rate"],
                total_backtest_trades=result["matched_count"] + result["unmatched_backtest_count"],
                total_live_trades=result["matched_count"] + result["unmatched_live_count"],
                details_json=json.dumps(result, default=str),
            )
            session.add(rec)
            session.commit()
            session.close()
        except Exception as exc:
            logger.error(f"Failed to save reconciliation result: {exc}")
