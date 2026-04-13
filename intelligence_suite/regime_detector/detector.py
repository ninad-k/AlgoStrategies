"""
Market Regime Detector
========================
Classifies the current market state into one of:
    TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, BREAKOUT

Supports rule-based detection and optional HMM.
"""

import logging
from datetime import datetime

import pandas as pd

from .features import extract_regime_features

logger = logging.getLogger(__name__)


class RegimeDetector:
    REGIMES = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE", "BREAKOUT"]

    def __init__(self, config: dict):
        self.config = config.get("regime", {})
        self.method = self.config.get("method", "rule_based")
        self.history = []  # List of (timestamp, symbol, regime, features)
        self.hmm_model = None

        if self.method == "hmm":
            self._init_hmm()

    def _init_hmm(self):
        """Initialize Hidden Markov Model for regime detection."""
        try:
            from hmmlearn.hmm import GaussianHMM
            self.hmm_model = GaussianHMM(
                n_components=5,  # 5 regimes
                covariance_type="diag",
                n_iter=100,
                random_state=42,
            )
            logger.info("HMM regime detector initialized")
        except ImportError:
            logger.warning("hmmlearn not installed, falling back to rule-based")
            self.method = "rule_based"

    def detect(self, df: pd.DataFrame, symbol: str = "") -> dict:
        """
        Detect current market regime.

        Returns:
            dict with regime, confidence, features, timestamp
        """
        features = extract_regime_features(df)
        if not features:
            return {"regime": "RANGING", "confidence": 0.0, "features": {}}

        if self.method == "hmm" and self.hmm_model is not None:
            regime, confidence = self._detect_hmm(df, features)
        else:
            regime, confidence = self._detect_rule_based(features)

        result = {
            "regime": regime,
            "confidence": round(confidence, 2),
            "features": features,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }

        self.history.append(result)
        if len(self.history) > 1000:
            self.history = self.history[-500:]

        return result

    def _detect_rule_based(self, f: dict) -> tuple[str, float]:
        """
        Rule-based regime classification.

        Decision tree:
        1. BREAKOUT: ATR ratio > 1.8 AND volume surge (>2x)
        2. VOLATILE: ATR ratio > 1.5 OR return_std very high
        3. TRENDING_UP: ADX > 25, directional bias > +1.5, consistency > 0.7
        4. TRENDING_DOWN: ADX > 25, directional bias < -1.5, consistency > 0.7
        5. RANGING: default (ADX < 20, low volatility)
        """
        adx = f.get("adx", 0)
        atr_ratio = f.get("atr_ratio", 1.0)
        vol_ratio = f.get("vol_ratio", 1.0)
        bb_width = f.get("bb_width_pct", 0)
        return_std = f.get("return_std", 0)
        bias = f.get("directional_bias", 0)
        consistency = f.get("candle_consistency", 0.5)

        # Breakout: sudden volatility expansion + volume
        if atr_ratio > 1.8 and vol_ratio > 2.0:
            conf = min(0.95, 0.6 + (atr_ratio - 1.8) * 0.5 + (vol_ratio - 2.0) * 0.1)
            return "BREAKOUT", conf

        # Volatile: high ATR ratio or wide BBs without clear direction
        if atr_ratio > 1.5 or (return_std > 0.005 and adx < 25):
            conf = min(0.9, 0.5 + (atr_ratio - 1.0) * 0.3)
            return "VOLATILE", conf

        # Strong trend up
        if adx > 25 and bias > 1.5 and consistency > 0.7:
            conf = min(0.95, 0.5 + (adx - 25) * 0.01 + bias * 0.05)
            return "TRENDING_UP", conf

        # Strong trend down
        if adx > 25 and bias < -1.5 and consistency > 0.7:
            conf = min(0.95, 0.5 + (adx - 25) * 0.01 + abs(bias) * 0.05)
            return "TRENDING_DOWN", conf

        # Moderate trend
        if adx > 20 and abs(bias) > 0.8:
            regime = "TRENDING_UP" if bias > 0 else "TRENDING_DOWN"
            conf = 0.4 + (adx - 20) * 0.01
            return regime, min(0.7, conf)

        # Default: ranging
        conf = 0.5 + max(0, (25 - adx) * 0.01)
        return "RANGING", min(0.85, conf)

    def _detect_hmm(self, df: pd.DataFrame, features: dict) -> tuple[str, float]:
        """HMM-based regime detection."""
        import numpy as np

        feature_cols = [
            features.get("atr_ratio", 1.0),
            features.get("adx", 20),
            features.get("bb_width_pct", 2),
            features.get("vol_ratio", 1.0),
            features.get("return_std", 0.001),
        ]

        X = np.array([feature_cols]).reshape(-1, 1) if len(feature_cols) == 1 else np.array([feature_cols])

        try:
            # If not fitted, use rule-based as fallback
            if not hasattr(self.hmm_model, "means_"):
                return self._detect_rule_based(features)

            state = int(self.hmm_model.predict(X)[0])
            probs = self.hmm_model.predict_proba(X)[0]
            confidence = float(max(probs))

            regime_map = {
                0: "TRENDING_UP", 1: "TRENDING_DOWN",
                2: "RANGING", 3: "VOLATILE", 4: "BREAKOUT",
            }
            return regime_map.get(state, "RANGING"), confidence

        except Exception as e:
            logger.warning(f"HMM prediction failed: {e}")
            return self._detect_rule_based(features)

    def get_history(self, symbol: str = None, limit: int = 50) -> list:
        """Get recent regime history."""
        history = self.history
        if symbol:
            history = [h for h in history if h.get("symbol") == symbol]
        return history[-limit:]

    def get_current_regime(self, symbol: str) -> str:
        """Get the last detected regime for a symbol."""
        for entry in reversed(self.history):
            if entry.get("symbol") == symbol:
                return entry["regime"]
        return "RANGING"
