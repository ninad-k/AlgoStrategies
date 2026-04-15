# ML Signal Generator
# Author: Ninad
#
# Replaces the original K-Means clustering approach with trained XGBoost models.
# Loads a per-timeframe model and generates BUY/SELL/HOLD predictions from
# the same SuperTrend + multi-TF features used during training.

import logging
import numpy as np
import pandas as pd
from typing import Optional, Dict

from .ml_trainer import load_trained_model
from .feature_engine import build_full_feature_matrix
from .data_fetcher import add_base_indicators

logger = logging.getLogger(__name__)

# Reverse label map (XGBoost classes -> trade direction)
LABEL_TO_SIGNAL = {0: -1, 1: 0, 2: 1}  # 0=short, 1=no-trade, 2=long


class MLSignalGenerator:
    """Generates trade signals using trained ML models instead of K-Means clustering."""

    def __init__(self, symbol: str, model_dir: str = "models"):
        self.symbol = symbol
        self.model_dir = model_dir
        self._models = {}
        self._scalers = {}

    def load_model(self, tf_name: str) -> bool:
        """Load a trained model for the given timeframe. Returns True on success."""
        try:
            model, scaler = load_trained_model(self.symbol, tf_name, self.model_dir)
            self._models[tf_name] = model
            self._scalers[tf_name] = scaler
            logger.info(f"Loaded model for {self.symbol} {tf_name}")
            return True
        except FileNotFoundError:
            logger.warning(f"No model found for {self.symbol} {tf_name}")
            return False

    def predict(
        self,
        tf_name: str,
        target_df: pd.DataFrame,
        higher_tf_data: Dict[str, pd.DataFrame] = None,
    ) -> dict:
        """Run prediction on the latest bar.

        Returns dict with:
            signal: 1 (buy), -1 (sell), 0 (hold)
            confidence: model's probability for the predicted class
            probabilities: {short, hold, long} probabilities
        """
        if tf_name not in self._models:
            if not self.load_model(tf_name):
                return {"signal": 0, "confidence": 0.0, "probabilities": {}}

        model = self._models[tf_name]
        scaler = self._scalers[tf_name]

        # Prepare higher TF data with indicators
        htf_processed = {}
        if higher_tf_data:
            for htf_name, htf_df in higher_tf_data.items():
                htf_processed[htf_name] = add_base_indicators(htf_df)

        # Build features (same pipeline as training)
        X, _ = build_full_feature_matrix(
            target_df,
            higher_tf_data=htf_processed,
            forward_bars=1,     # minimal, we only need features not labels
            min_move_atr=1.0,
        )

        if len(X) == 0:
            return {"signal": 0, "confidence": 0.0, "probabilities": {}}

        # Use only the latest row
        latest = X.iloc[[-1]]

        # Align columns with what the model expects
        model_features = model.get_booster().feature_names if hasattr(model, 'get_booster') else None
        if model_features:
            missing = set(model_features) - set(latest.columns)
            for col in missing:
                latest[col] = 0
            latest = latest[model_features]

        # Scale and predict
        latest_scaled = scaler.transform(latest)

        prediction = int(model.predict(latest_scaled)[0])
        signal = LABEL_TO_SIGNAL.get(prediction, 0)

        # Get prediction probabilities
        proba = {}
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(latest_scaled)[0]
            proba = {
                "short": round(float(probabilities[0]), 4),
                "hold": round(float(probabilities[1]), 4) if len(probabilities) > 2 else 0.0,
                "long": round(float(probabilities[-1]), 4),
            }
            confidence = float(probabilities[prediction])
        else:
            confidence = 1.0

        result = {
            "signal": signal,
            "confidence": round(confidence, 4),
            "probabilities": proba,
        }

        signal_name = {1: "BUY", -1: "SELL", 0: "HOLD"}
        logger.info(
            f"ML Signal [{tf_name}]: {signal_name[signal]} "
            f"(conf={confidence:.2%}, proba={proba})"
        )

        return result


class MultiTimeframeSignal:
    """Combines ML predictions across multiple timeframes into a consensus signal.

    Uses a weighted voting scheme where higher timeframes carry more weight
    since they represent stronger structural trends.
    """

    TIMEFRAME_WEIGHTS = {
        "M1": 0.5, "M5": 0.7, "M15": 1.0, "M30": 1.2,
        "H1": 1.5, "H4": 2.0, "D1": 2.5, "W1": 3.0, "MN1": 3.5,
    }

    def __init__(self, symbol: str, timeframes: list, model_dir: str = "models"):
        self.generator = MLSignalGenerator(symbol, model_dir)
        self.timeframes = timeframes

        # Pre-load all models
        for tf in timeframes:
            self.generator.load_model(tf)

    def get_consensus(
        self,
        data_by_tf: Dict[str, pd.DataFrame],
        higher_tf_data: Dict[str, pd.DataFrame] = None,
        min_confidence: float = 0.5,
    ) -> dict:
        """Get weighted consensus signal across all loaded timeframes.

        Returns:
            signal: 1, -1, or 0
            consensus_score: weighted average (-1 to +1, positive = bullish)
            per_timeframe: individual predictions
        """
        predictions = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for tf_name in self.timeframes:
            if tf_name not in data_by_tf:
                continue

            result = self.generator.predict(
                tf_name,
                data_by_tf[tf_name],
                higher_tf_data=higher_tf_data,
            )

            predictions[tf_name] = result
            weight = self.TIMEFRAME_WEIGHTS.get(tf_name, 1.0)

            if result["confidence"] >= min_confidence:
                weighted_sum += result["signal"] * weight * result["confidence"]
                total_weight += weight

        consensus_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Convert score to discrete signal
        if consensus_score > 0.3:
            signal = 1
        elif consensus_score < -0.3:
            signal = -1
        else:
            signal = 0

        signal_name = {1: "BUY", -1: "SELL", 0: "HOLD"}
        logger.info(
            f"MTF Consensus: {signal_name[signal]} "
            f"(score={consensus_score:.4f}, TFs={len(predictions)})"
        )

        return {
            "signal": signal,
            "consensus_score": round(consensus_score, 4),
            "per_timeframe": predictions,
        }
