"""
Ensemble Engine — Combines decisions from multiple models.

Voting methods:
- weighted_average: Weighted mean of confidences, majority action.
- majority_vote: Simple majority wins (2 of 3).
- veto: Any model with high-confidence HOLD vetoes the trade.
"""

import logging
from datetime import datetime
from collections import Counter

from .base_analyzer import BaseAnalyzer
from .gemma_analyzer import GemmaAnalyzer
from .llama_analyzer import LlamaAnalyzer
from .onnx_analyzer import OnnxAnalyzer

logger = logging.getLogger(__name__)


class EnsembleEngine:
    def __init__(self, config: dict):
        self.config = config
        self.ensemble_cfg = config.get("ensemble", {})
        self.models_cfg = config.get("models", {})

        # Initialize model adapters
        self.analyzers: list[BaseAnalyzer] = []
        self._init_analyzers()

        # Per-model performance tracking for dynamic weights
        self.model_stats = {}  # model_name -> {"wins": 0, "losses": 0, "total": 0}

    def _init_analyzers(self):
        """Initialize enabled model analyzers."""
        if self.models_cfg.get("gemma", {}).get("enabled", True):
            self.analyzers.append(GemmaAnalyzer(self.models_cfg.get("gemma", {})))

        if self.models_cfg.get("llama", {}).get("enabled", True):
            self.analyzers.append(LlamaAnalyzer(self.models_cfg.get("llama", {})))

        if self.models_cfg.get("onnx", {}).get("enabled", True):
            self.analyzers.append(OnnxAnalyzer(self.models_cfg.get("onnx", {})))

        logger.info(f"Ensemble initialized with {len(self.analyzers)} models: "
                     f"{[a.name for a in self.analyzers]}")

    def analyze(self, market_data: dict) -> dict:
        """
        Run all models on market_data and combine decisions.

        Returns an ensemble decision dict with:
            final_action, final_confidence, sl_distance_atr, tp_distance_atr,
            reason, individual_decisions, vote_summary, model_weights
        """
        decisions = []

        for analyzer in self.analyzers:
            try:
                if not analyzer.is_available():
                    logger.warning(f"{analyzer.name} unavailable, skipping")
                    continue
                decision = analyzer.analyze(market_data, self.config)
                decisions.append(decision)
                logger.info(
                    f"  {analyzer.name}: {decision['action']} "
                    f"(conf={decision['confidence']:.2f}) — {decision.get('reason', '')[:60]}"
                )
            except Exception as e:
                logger.error(f"  {analyzer.name} failed: {e}")

        if not decisions:
            return self._hold_result(market_data, "no models available")

        # Get model weights
        weights = self._get_weights(decisions)

        # Apply voting method
        method = self.ensemble_cfg.get("voting_method", "weighted_average")
        if method == "majority_vote":
            result = self._majority_vote(decisions, weights, market_data)
        elif method == "veto":
            result = self._veto_vote(decisions, weights, market_data)
        else:
            result = self._weighted_average(decisions, weights, market_data)

        result["individual_decisions"] = decisions
        result["model_weights"] = weights
        return result

    def _get_weights(self, decisions: list) -> dict:
        """Get model weights — dynamic based on win rates, or from config."""
        weights = {}
        use_dynamic = self.ensemble_cfg.get("dynamic_weights", False)

        for d in decisions:
            model = d.get("model_name", "unknown")

            if use_dynamic and model in self.model_stats:
                stats = self.model_stats[model]
                total = stats["total"]
                if total >= 5:
                    win_rate = stats["wins"] / total
                    weights[model] = max(0.1, win_rate)
                    continue

            # Fallback to config weights
            weights[model] = self.models_cfg.get(model, {}).get("weight", 1.0 / len(decisions))

        # Normalize
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        return weights

    def _weighted_average(self, decisions: list, weights: dict, market_data: dict) -> dict:
        """Weighted average of confidences, majority action."""
        # Separate directional decisions from HOLDs
        directional = [d for d in decisions if d["action"] != "HOLD"]
        holds = [d for d in decisions if d["action"] == "HOLD"]

        min_agreement = self.ensemble_cfg.get("min_agreement", 2)

        if len(directional) < min_agreement:
            return self._hold_result(market_data, f"Only {len(directional)} directional votes (need {min_agreement})")

        # Count actions
        action_counts = Counter(d["action"] for d in directional)
        winning_action = action_counts.most_common(1)[0][0]

        # Weighted confidence for the winning action
        total_conf = 0
        total_weight = 0
        sl_sum, tp_sum = 0, 0
        reasons = []

        for d in directional:
            if d["action"] == winning_action:
                w = weights.get(d["model_name"], 1.0 / len(decisions))
                total_conf += d["confidence"] * w
                total_weight += w
                sl_sum += d.get("sl_distance_atr", 1.0) * w
                tp_sum += d.get("tp_distance_atr", 1.5) * w
                reasons.append(f"{d['model_name']}: {d.get('reason', '')[:40]}")

        final_conf = total_conf / total_weight if total_weight > 0 else 0
        final_sl = sl_sum / total_weight if total_weight > 0 else 1.0
        final_tp = tp_sum / total_weight if total_weight > 0 else 1.5

        vote_summary = {
            "BUY": sum(1 for d in decisions if d["action"] == "BUY"),
            "SELL": sum(1 for d in decisions if d["action"] == "SELL"),
            "HOLD": sum(1 for d in decisions if d["action"] == "HOLD"),
        }

        return {
            "final_action": winning_action,
            "final_confidence": round(final_conf, 4),
            "sl_distance_atr": round(final_sl, 2),
            "tp_distance_atr": round(final_tp, 2),
            "reason": " | ".join(reasons),
            "symbol": market_data.get("symbol", "UNKNOWN"),
            "timestamp": datetime.now().isoformat(),
            "vote_summary": vote_summary,
        }

    def _majority_vote(self, decisions: list, weights: dict, market_data: dict) -> dict:
        """Simple majority vote — most common action wins."""
        action_counts = Counter(d["action"] for d in decisions)
        winning_action = action_counts.most_common(1)[0][0]

        matching = [d for d in decisions if d["action"] == winning_action]
        avg_conf = sum(d["confidence"] for d in matching) / len(matching)
        avg_sl = sum(d.get("sl_distance_atr", 1.0) for d in matching) / len(matching)
        avg_tp = sum(d.get("tp_distance_atr", 1.5) for d in matching) / len(matching)

        vote_summary = {a: c for a, c in action_counts.items()}

        return {
            "final_action": winning_action,
            "final_confidence": round(avg_conf, 4),
            "sl_distance_atr": round(avg_sl, 2),
            "tp_distance_atr": round(avg_tp, 2),
            "reason": f"Majority vote: {vote_summary}",
            "symbol": market_data.get("symbol", "UNKNOWN"),
            "timestamp": datetime.now().isoformat(),
            "vote_summary": vote_summary,
        }

    def _veto_vote(self, decisions: list, weights: dict, market_data: dict) -> dict:
        """Veto: any model with high-confidence HOLD vetoes the trade."""
        veto_conf = self.ensemble_cfg.get("veto_confidence", 0.85)

        for d in decisions:
            if d["action"] == "HOLD" and d["confidence"] >= veto_conf:
                return self._hold_result(
                    market_data,
                    f"Vetoed by {d['model_name']} (HOLD conf={d['confidence']:.2f})"
                )

        # No veto — fall through to weighted average
        return self._weighted_average(decisions, weights, market_data)

    def _hold_result(self, market_data: dict, reason: str) -> dict:
        return {
            "final_action": "HOLD", "final_confidence": 0.0,
            "sl_distance_atr": 0, "tp_distance_atr": 0,
            "reason": reason,
            "symbol": market_data.get("symbol", "UNKNOWN"),
            "timestamp": datetime.now().isoformat(),
            "vote_summary": {}, "individual_decisions": [], "model_weights": {},
        }

    def record_outcome(self, model_name: str, is_win: bool):
        """Track per-model win/loss for dynamic weight adjustment."""
        if model_name not in self.model_stats:
            self.model_stats[model_name] = {"wins": 0, "losses": 0, "total": 0}
        stats = self.model_stats[model_name]
        stats["total"] += 1
        if is_win:
            stats["wins"] += 1
        else:
            stats["losses"] += 1

    def get_model_stats(self) -> dict:
        """Return per-model performance stats."""
        result = {}
        for model, stats in self.model_stats.items():
            total = stats["total"]
            result[model] = {
                **stats,
                "win_rate": round(stats["wins"] / total * 100, 1) if total > 0 else 0,
            }
        return result
