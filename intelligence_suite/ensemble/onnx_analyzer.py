"""
ONNX Analyzer — Fast LightGBM model for sub-second directional signals.
Uses a pre-trained ONNX model for quick classification.
"""

import logging
from datetime import datetime

import numpy as np

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class OnnxAnalyzer(BaseAnalyzer):
    name = "onnx"

    def __init__(self, model_config: dict = None):
        self.model_config = model_config or {}
        self.session = None
        self._load_model()

    def _load_model(self):
        model_path = self.model_config.get("model_path", "")
        if not model_path:
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(model_path)
            logger.info(f"ONNX model loaded: {model_path}")
        except FileNotFoundError:
            logger.warning(f"ONNX model not found at {model_path}")
        except Exception as e:
            logger.warning(f"Failed to load ONNX model: {e}")

    def is_available(self) -> bool:
        return self.session is not None

    def analyze(self, market_data: dict, config: dict) -> dict:
        if not self.session:
            return self._from_indicators(market_data)

        try:
            features = self._extract_features(market_data)
            input_name = self.session.get_inputs()[0].name
            result = self.session.run(None, {input_name: features})

            # LightGBM ONNX output: [class_id] and [[prob_class0, prob_class1, ...]]
            pred_class = int(result[0][0])
            probabilities = result[1][0] if len(result) > 1 else [0.5, 0.5]

            action_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
            action = action_map.get(pred_class, "HOLD")
            confidence = float(max(probabilities))

            return {
                "action": action,
                "confidence": round(confidence, 4),
                "sl_distance_atr": 1.0,
                "tp_distance_atr": 1.5,
                "reason": f"ONNX model pred={pred_class} conf={confidence:.2f}",
                "model_name": "onnx",
                "symbol": market_data.get("symbol", "UNKNOWN"),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            return self._from_indicators(market_data)

    def _extract_features(self, data: dict) -> np.ndarray:
        """Extract feature vector matching the training schema."""
        feature_keys = [
            "rsi", "macd", "macd_signal", "macd_hist",
            "adx", "di_plus", "di_minus",
            "cci", "williams_r", "mfi", "roc",
            "stoch_rsi_k", "stoch_rsi_d", "stoch_k", "stoch_d",
            "atr", "bb_width", "vol_ratio",
            "ema9", "ema20", "ema50", "ema200",
        ]
        values = [float(data.get(k, 0)) for k in feature_keys]
        return np.array([values], dtype=np.float32)

    def _from_indicators(self, data: dict) -> dict:
        """
        Rule-based fallback when ONNX model is unavailable.
        Simple signal scoring based on indicators.
        """
        score = 0
        reasons = []

        # RSI
        rsi = float(data.get("rsi", 50))
        if rsi < 30:
            score += 2
            reasons.append("RSI oversold")
        elif rsi > 70:
            score -= 2
            reasons.append("RSI overbought")

        # MACD
        macd_hist = float(data.get("macd_hist", 0))
        if macd_hist > 0:
            score += 1
            reasons.append("MACD bullish")
        elif macd_hist < 0:
            score -= 1
            reasons.append("MACD bearish")

        # Trend
        trend = data.get("trend", "MIXED")
        if "BULLISH" in trend:
            score += 1
        elif "BEARISH" in trend:
            score -= 1

        # Ichimoku
        ich = data.get("ichimoku_signal", "")
        if "BULLISH" in ich:
            score += 1
        elif "BEARISH" in ich:
            score -= 1

        # Volume
        vol = data.get("vol_trend", "LOW")
        if vol in ("SURGE", "HIGH"):
            score = int(score * 1.5) if score != 0 else score

        # Convert score to action
        if score >= 3:
            action, confidence = "BUY", min(0.5 + score * 0.05, 0.9)
        elif score <= -3:
            action, confidence = "SELL", min(0.5 + abs(score) * 0.05, 0.9)
        else:
            action, confidence = "HOLD", 0.3

        return {
            "action": action,
            "confidence": round(confidence, 2),
            "sl_distance_atr": 1.0,
            "tp_distance_atr": 1.5,
            "reason": "; ".join(reasons) if reasons else "weak signals",
            "model_name": "onnx",
            "symbol": data.get("symbol", "UNKNOWN"),
            "timestamp": datetime.now().isoformat(),
        }
