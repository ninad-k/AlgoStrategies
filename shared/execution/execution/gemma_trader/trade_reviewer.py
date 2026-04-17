"""
Rey Capital AI Bot — Trade Reviewer (Self-Improving Logic)
============================================================
Analyzes trade outcomes, builds adaptive context for Gemma,
and triggers dynamic parameter adjustments.

Key features:
  - Performance analysis: win rate, profit factor, per-symbol stats
  - Adaptive prompt engineering: builds a context block for Gemma
    based on what worked / what didn't
  - Dynamic parameter adjustment via RiskManager
  - Weekly meta-review: feeds Gemma its own trade history for self-reflection
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from gemma_analyzer import review_trades_with_gemma

logger = logging.getLogger("trade_reviewer")


class TradeReviewer:
    """
    Analyzes completed trades and generates adaptive context
    that gets prepended to Gemma's system prompt.
    """

    def __init__(self, config: dict, risk_manager=None):
        self.config = config
        self.risk_manager = risk_manager
        self.adaptive_cfg = config.get("adaptive", {})

        log_cfg = config.get("logging", {})
        self.outcome_path = Path(log_cfg.get("outcome_log", "logs/trade_outcomes.json"))
        self.adaptive_ctx_path = Path(log_cfg.get("adaptive_context", "logs/adaptive_context.txt"))
        self.param_adj_path = Path(log_cfg.get("parameter_adjustments", "logs/parameter_adjustments.json"))

        self.last_review_count = 0
        self.last_weekly_review = None

    # ─── Performance Analysis ───

    def analyze_performance(self, force: bool = False) -> dict:
        """
        Analyze trade outcomes and generate adaptive context.
        Called after every N trades (configurable) or on demand.

        Returns performance summary dict.
        """
        outcomes = self._load_outcomes()
        if not outcomes:
            return {}

        # Check if we need to review (every N trades)
        review_every = self.adaptive_cfg.get("review_every_n_trades", 10)
        if not force and len(outcomes) - self.last_review_count < review_every:
            return {}

        self.last_review_count = len(outcomes)
        logger.info(f"Analyzing performance: {len(outcomes)} trades")

        # ── Overall Stats ──
        wins = [o for o in outcomes if o.get("profit", 0) > 0]
        losses = [o for o in outcomes if o.get("profit", 0) <= 0]
        total = len(outcomes)

        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = sum(o["profit"] for o in wins) / len(wins) if wins else 0
        avg_loss = sum(o["profit"] for o in losses) / len(losses) if losses else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        total_pnl = sum(o.get("profit", 0) for o in outcomes)

        # ── Per-Symbol Stats ──
        symbol_stats = {}
        for o in outcomes:
            sym = o.get("symbol", "?")
            if sym not in symbol_stats:
                symbol_stats[sym] = {
                    "wins": 0, "losses": 0, "total_pnl": 0,
                    "actions": {"BUY": {"wins": 0, "losses": 0},
                                "SELL": {"wins": 0, "losses": 0}},
                }
            ss = symbol_stats[sym]
            is_win = o.get("profit", 0) > 0
            if is_win:
                ss["wins"] += 1
            else:
                ss["losses"] += 1
            ss["total_pnl"] += o.get("profit", 0)

            action = o.get("action", "BUY")
            if action in ss["actions"]:
                if is_win:
                    ss["actions"][action]["wins"] += 1
                else:
                    ss["actions"][action]["losses"] += 1

        for sym in symbol_stats:
            ss = symbol_stats[sym]
            t = ss["wins"] + ss["losses"]
            ss["win_rate"] = round(ss["wins"] / t * 100, 1) if t > 0 else 0

        # ── Indicator Pattern Analysis ──
        indicator_patterns = self._analyze_indicator_patterns(outcomes)

        # ── Build Adaptive Context ──
        context = self._build_adaptive_context(
            win_rate, avg_win, avg_loss, profit_factor, total_pnl,
            symbol_stats, indicator_patterns, total,
        )
        self._save_adaptive_context(context)

        # ── Dynamic Threshold Adjustment ──
        if self.risk_manager:
            # Use last 20 trades for threshold adjustment
            recent = outcomes[-20:]
            recent_wins = sum(1 for o in recent if o.get("profit", 0) > 0)
            recent_wr = recent_wins / len(recent) * 100 if recent else 0
            self.risk_manager.adjust_threshold(recent_wr, len(recent))

        summary = {
            "total_trades": total,
            "win_rate": round(win_rate, 1),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "total_pnl": round(total_pnl, 2),
            "symbol_stats": symbol_stats,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"Performance: WR={win_rate:.1f}% | PF={profit_factor:.2f} | "
            f"Total PnL=${total_pnl:.2f}"
        )

        return summary

    def _analyze_indicator_patterns(self, outcomes: list) -> list:
        """
        Analyze which indicator combinations correlate with wins/losses.
        Returns a list of human-readable patterns.
        """
        patterns = []

        # Analyze RSI ranges for wins vs losses
        rsi_bins = {"oversold (<30)": {"wins": 0, "losses": 0},
                     "neutral (30-70)": {"wins": 0, "losses": 0},
                     "overbought (>70)": {"wins": 0, "losses": 0}}

        trend_results = {}
        ichimoku_results = {}
        vol_results = {}

        for o in outcomes:
            snap = o.get("indicators_snapshot", {})
            is_win = o.get("profit", 0) > 0

            # RSI
            rsi = snap.get("rsi")
            if rsi is not None:
                if rsi < 30:
                    rsi_bins["oversold (<30)"]["wins" if is_win else "losses"] += 1
                elif rsi > 70:
                    rsi_bins["overbought (>70)"]["wins" if is_win else "losses"] += 1
                else:
                    rsi_bins["neutral (30-70)"]["wins" if is_win else "losses"] += 1

            # Trend
            trend = snap.get("trend", "UNKNOWN")
            if trend not in trend_results:
                trend_results[trend] = {"wins": 0, "losses": 0}
            trend_results[trend]["wins" if is_win else "losses"] += 1

            # Ichimoku
            ichi = snap.get("ichimoku_signal", "UNKNOWN")
            if ichi not in ichimoku_results:
                ichimoku_results[ichi] = {"wins": 0, "losses": 0}
            ichimoku_results[ichi]["wins" if is_win else "losses"] += 1

            # Volume
            vol = snap.get("vol_trend", "UNKNOWN")
            if vol not in vol_results:
                vol_results[vol] = {"wins": 0, "losses": 0}
            vol_results[vol]["wins" if is_win else "losses"] += 1

        # Generate pattern insights
        for label, data in rsi_bins.items():
            total = data["wins"] + data["losses"]
            if total >= 3:
                wr = data["wins"] / total * 100
                if wr >= 65:
                    patterns.append(f"RSI {label}: {wr:.0f}% win rate ({total} trades) — FAVORABLE")
                elif wr <= 35:
                    patterns.append(f"RSI {label}: {wr:.0f}% win rate ({total} trades) — AVOID")

        for trend, data in trend_results.items():
            total = data["wins"] + data["losses"]
            if total >= 3:
                wr = data["wins"] / total * 100
                if wr >= 65:
                    patterns.append(f"Trend={trend}: {wr:.0f}% win rate — trade with trend")
                elif wr <= 35:
                    patterns.append(f"Trend={trend}: {wr:.0f}% win rate — avoid counter-trend")

        for sig, data in ichimoku_results.items():
            total = data["wins"] + data["losses"]
            if total >= 3:
                wr = data["wins"] / total * 100
                if wr >= 65:
                    patterns.append(f"Ichimoku {sig}: {wr:.0f}% win rate — good signal")
                elif wr <= 35:
                    patterns.append(f"Ichimoku {sig}: {wr:.0f}% win rate — unreliable signal")

        for vol, data in vol_results.items():
            total = data["wins"] + data["losses"]
            if total >= 3:
                wr = data["wins"] / total * 100
                if wr >= 65:
                    patterns.append(f"Volume {vol}: {wr:.0f}% win rate — confirm entries with this volume")
                elif wr <= 35:
                    patterns.append(f"Volume {vol}: {wr:.0f}% win rate — avoid entries at this volume")

        return patterns

    def _build_adaptive_context(self, win_rate, avg_win, avg_loss,
                                 profit_factor, total_pnl,
                                 symbol_stats, indicator_patterns, total):
        """Build the adaptive context string that gets prepended to Gemma's prompt."""
        lines = [
            f"LESSONS FROM RECENT TRADES (auto-updated {datetime.now().strftime('%Y-%m-%d %H:%M')}):",
            f"- Overall: {total} trades | Win rate: {win_rate:.1f}% | "
            f"Avg win: ${avg_win:.2f} | Avg loss: ${avg_loss:.2f} | "
            f"Profit factor: {profit_factor:.2f}",
        ]

        # Win rate guidance
        if win_rate < 40:
            lines.append(
                f"- CAUTION: Win rate is LOW ({win_rate:.1f}%). "
                f"Be MORE selective. Only take HIGH confluence setups."
            )
        elif win_rate > 60:
            lines.append(
                f"- GOOD: Win rate is strong ({win_rate:.1f}%). "
                f"Continue current approach. Can take moderate setups."
            )

        # Per-symbol insights
        best_sym = max(symbol_stats, key=lambda s: symbol_stats[s]["win_rate"], default=None)
        worst_sym = min(symbol_stats, key=lambda s: symbol_stats[s]["win_rate"], default=None)

        if best_sym:
            ss = symbol_stats[best_sym]
            lines.append(
                f"- Best: {best_sym} ({ss['win_rate']}% WR, "
                f"${ss['total_pnl']:.2f} PnL)"
            )

        if worst_sym and worst_sym != best_sym:
            ss = symbol_stats[worst_sym]
            if ss["win_rate"] < 40:
                lines.append(
                    f"- Worst: {worst_sym} ({ss['win_rate']}% WR, "
                    f"${ss['total_pnl']:.2f} PnL) — consider being more cautious"
                )

        # Per-symbol action insights
        for sym, ss in symbol_stats.items():
            for action in ["BUY", "SELL"]:
                a = ss["actions"][action]
                t = a["wins"] + a["losses"]
                if t >= 3:
                    wr = a["wins"] / t * 100
                    if wr <= 30:
                        lines.append(
                            f"- AVOID: {sym} {action} signals "
                            f"({wr:.0f}% win rate over {t} trades)"
                        )
                    elif wr >= 70:
                        lines.append(
                            f"- FAVOR: {sym} {action} signals "
                            f"({wr:.0f}% win rate over {t} trades)"
                        )

        # Indicator patterns
        for pattern in indicator_patterns[:6]:
            lines.append(f"- {pattern}")

        return "\n".join(lines)

    # ─── Weekly Meta-Review (Gemma Reviews Itself) ───

    def weekly_review(self, force: bool = False) -> str:
        """
        Feed Gemma its own trade history for meta-analysis.
        Returns updated lessons learned.
        """
        if not self.adaptive_cfg.get("weekly_review", True) and not force:
            return ""

        # Check if it's time (once a week or forced)
        now = datetime.now()
        if not force and self.last_weekly_review:
            days_since = (now - self.last_weekly_review).days
            if days_since < 7:
                return ""

        outcomes = self._load_outcomes()
        if len(outcomes) < 10:
            return ""

        logger.info("Running weekly Gemma self-review...")
        self.last_weekly_review = now

        # Feed last 50 trades to Gemma for meta-analysis
        lessons = review_trades_with_gemma(outcomes[-50:], self.config)

        if lessons:
            # Merge with existing adaptive context
            existing = ""
            try:
                if self.adaptive_ctx_path.exists():
                    existing = self.adaptive_ctx_path.read_text().strip()
            except Exception:
                pass

            # Combine: keep auto-generated stats + add Gemma's meta-review
            combined = existing
            if combined:
                combined += "\n\n"
            combined += f"GEMMA SELF-REVIEW ({now.strftime('%Y-%m-%d')}):\n{lessons}"

            self._save_adaptive_context(combined)
            logger.info(f"Weekly review complete: {len(lessons)} chars of lessons")

        return lessons

    # ─── Helpers ───

    def _load_outcomes(self) -> list:
        """Load trade outcomes from log."""
        try:
            if self.outcome_path.exists():
                text = self.outcome_path.read_text(encoding="utf-8-sig").strip()
                if text:
                    return json.loads(text)
        except Exception as e:
            logger.error(f"Failed to load outcomes: {e}")
        return []

    def _save_adaptive_context(self, context: str):
        """Save adaptive context to file."""
        try:
            self.adaptive_ctx_path.parent.mkdir(parents=True, exist_ok=True)
            self.adaptive_ctx_path.write_text(context)
            logger.debug(f"Adaptive context saved ({len(context)} chars)")
        except Exception as e:
            logger.error(f"Failed to save adaptive context: {e}")

    def get_performance_summary(self) -> dict:
        """Get a quick performance summary without triggering full analysis."""
        outcomes = self._load_outcomes()
        if not outcomes:
            return {"total": 0, "win_rate": 0, "total_pnl": 0}

        wins = sum(1 for o in outcomes if o.get("profit", 0) > 0)
        total = len(outcomes)
        total_pnl = sum(o.get("profit", 0) for o in outcomes)

        return {
            "total": total,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_pnl": round(total_pnl, 2),
        }
