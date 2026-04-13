"""
ReySentinel — Compliance Reporter
===========================================
Generates CSV exports and summary statistics for regulatory compliance
and internal audit review.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ComplianceReporter:
    """Generates compliance reports from trade audit data."""

    CSV_COLUMNS = [
        "trade_id",
        "timestamp",
        "symbol",
        "action",
        "qty",
        "entry_price",
        "exit_price",
        "pnl",
        "model_decision",
        "confidence",
        "sl",
        "tp",
        "duration",
    ]

    def generate_csv(
        self,
        trades: list[dict[str, Any]],
        output_path: str = "exports/compliance_report.csv",
    ) -> str:
        """
        Export trades to a CSV file with compliance-required columns.

        Parameters
        ----------
        trades : list[dict]
            Trade records with fields matching CSV_COLUMNS.
        output_path : str
            Destination file path.

        Returns
        -------
        str : Absolute path to the generated CSV file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.CSV_COLUMNS,
                    extrasaction="ignore",
                )
                writer.writeheader()

                for trade in trades:
                    row = self._normalize_trade(trade)
                    writer.writerow(row)

            abs_path = str(out.resolve())
            logger.info(
                f"Compliance CSV exported: {abs_path} ({len(trades)} trades)"
            )
            return abs_path
        except Exception as exc:
            logger.error(f"Failed to generate compliance CSV: {exc}")
            raise

    def generate_summary(
        self,
        trades: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate summary statistics for compliance review.

        Parameters
        ----------
        trades : list[dict]
            Trade records.

        Returns
        -------
        dict with aggregated compliance statistics.
        """
        if not trades:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "total_trades": 0,
                "warning": "No trades to summarize",
            }

        normalized = [self._normalize_trade(t) for t in trades]

        # P&L calculations
        pnls = [float(t.get("pnl", 0)) for t in normalized]
        total_pnl = sum(pnls)
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        # Duration calculations
        durations = []
        for t in normalized:
            dur = t.get("duration")
            if dur is not None:
                try:
                    durations.append(float(dur))
                except (ValueError, TypeError):
                    pass

        # Symbol breakdown
        symbol_counts: dict[str, int] = {}
        symbol_pnl: dict[str, float] = {}
        for t in normalized:
            sym = t.get("symbol", "UNKNOWN")
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
            symbol_pnl[sym] = symbol_pnl.get(sym, 0.0) + float(t.get("pnl", 0))

        # Action breakdown
        action_counts: dict[str, int] = {}
        for t in normalized:
            act = t.get("action", "UNKNOWN")
            action_counts[act] = action_counts.get(act, 0) + 1

        # Model breakdown
        model_counts: dict[str, int] = {}
        for t in normalized:
            model = t.get("model_decision", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1

        # Confidence stats
        confidences = []
        for t in normalized:
            c = t.get("confidence")
            if c is not None:
                try:
                    confidences.append(float(c))
                except (ValueError, TypeError):
                    pass

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_trades": len(normalized),
            "total_pnl": round(total_pnl, 2),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "breakeven_trades": len(pnls) - len(winning) - len(losing),
            "win_rate": round(len(winning) / len(pnls) * 100, 2) if pnls else 0,
            "avg_pnl": round(total_pnl / len(pnls), 2) if pnls else 0,
            "max_win": round(max(winning), 2) if winning else 0,
            "max_loss": round(min(losing), 2) if losing else 0,
            "avg_win": round(sum(winning) / len(winning), 2) if winning else 0,
            "avg_loss": round(sum(losing) / len(losing), 2) if losing else 0,
            "profit_factor": round(
                abs(sum(winning) / sum(losing)), 2
            ) if losing and sum(losing) != 0 else float("inf") if winning else 0,
            "avg_duration_minutes": round(
                sum(durations) / len(durations), 2
            ) if durations else None,
            "avg_confidence": round(
                sum(confidences) / len(confidences), 4
            ) if confidences else None,
            "by_symbol": {
                sym: {"count": symbol_counts[sym], "pnl": round(symbol_pnl[sym], 2)}
                for sym in symbol_counts
            },
            "by_action": action_counts,
            "by_model": model_counts,
        }

        logger.info(
            f"Compliance summary: {len(normalized)} trades, "
            f"PnL={total_pnl:.2f}, WR={summary['win_rate']:.1f}%"
        )
        return summary

    def _normalize_trade(self, trade: dict) -> dict:
        """Normalize trade dict keys to match CSV_COLUMNS."""
        return {
            "trade_id": trade.get("trade_id", trade.get("ticket", "")),
            "timestamp": trade.get("timestamp", trade.get("entry_time", "")),
            "symbol": trade.get("symbol", ""),
            "action": trade.get("action", trade.get("type", "")),
            "qty": trade.get("qty", trade.get("volume", 0)),
            "entry_price": trade.get("entry_price", trade.get("price_open", 0)),
            "exit_price": trade.get("exit_price", trade.get("close_price", 0)),
            "pnl": trade.get("pnl", trade.get("profit", 0)),
            "model_decision": trade.get("model_decision", trade.get("model_name", "")),
            "confidence": trade.get("confidence", None),
            "sl": trade.get("sl", 0),
            "tp": trade.get("tp", 0),
            "duration": trade.get("duration", trade.get("duration_minutes", None)),
        }
