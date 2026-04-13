"""
Real-time Pattern Detector — Sliding window detection on live data.
"""

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .data_prep import ohlcv_to_image
from .patterns import LABEL_TO_PATTERN, PATTERN_CATALOG

logger = logging.getLogger(__name__)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class PatternDetector:
    def __init__(self, config: dict):
        pr_cfg = config.get("pattern_recognition", {})
        self.window_size = pr_cfg.get("window_size", 64)
        self.confidence_threshold = pr_cfg.get("confidence_threshold", 0.7)
        self.model = None
        self._load_model()

    def _load_model(self):
        if not TORCH_AVAILABLE:
            return

        model_path = Path("pattern_recognition/saved_models/pattern_cnn.pth")
        if not model_path.exists():
            logger.info("No trained pattern model found. Train one first.")
            return

        try:
            from .model import get_model
            self.model = get_model(self.window_size)
            self.model.load_state_dict(torch.load(model_path, weights_only=True))
            self.model.eval()
            logger.info(f"Pattern recognition model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load pattern model: {e}")

    def detect(self, df: pd.DataFrame, symbol: str = "") -> dict:
        """
        Detect patterns in the latest window of OHLCV data.

        Args:
            df: OHLCV DataFrame (should have at least window_size bars)
            symbol: Symbol name for labeling

        Returns:
            dict with pattern, confidence, direction, description
        """
        if df is None or len(df) < self.window_size:
            return {"pattern": "no_pattern", "confidence": 0, "direction": "NEUTRAL"}

        window = df.tail(self.window_size)

        if self.model is not None and TORCH_AVAILABLE:
            return self._detect_cnn(window, symbol)
        else:
            return self._detect_rule_based(window, symbol)

    def _detect_cnn(self, window: pd.DataFrame, symbol: str) -> dict:
        """CNN-based pattern detection."""
        image = ohlcv_to_image(window, self.window_size)
        tensor = torch.FloatTensor(image).unsqueeze(0).unsqueeze(0) / 255.0

        with torch.no_grad():
            output = self.model(tensor)
            probabilities = torch.softmax(output, dim=1)[0]
            confidence, predicted = torch.max(probabilities, 0)

        pattern_name = LABEL_TO_PATTERN.get(predicted.item(), "no_pattern")
        pattern_info = PATTERN_CATALOG.get(pattern_name, {})

        conf = float(confidence.item())
        if conf < self.confidence_threshold:
            pattern_name = "no_pattern"
            pattern_info = PATTERN_CATALOG["no_pattern"]

        return {
            "pattern": pattern_name,
            "confidence": round(conf, 3),
            "direction": pattern_info.get("direction", "NEUTRAL"),
            "description": pattern_info.get("description", ""),
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "method": "cnn",
            "all_probabilities": {
                LABEL_TO_PATTERN.get(i, f"class_{i}"): round(float(p), 3)
                for i, p in enumerate(probabilities)
                if float(p) > 0.05
            },
        }

    def _detect_rule_based(self, window: pd.DataFrame, symbol: str) -> dict:
        """
        Simple rule-based pattern detection as fallback.
        Uses swing highs/lows to identify basic patterns.
        """
        highs = window["high"].astype(float).values
        lows = window["low"].astype(float).values
        closes = window["close"].astype(float).values

        n = len(highs)
        mid = n // 2

        # Find swing points
        swing_highs = []
        swing_lows = []
        for i in range(2, n - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append((i, highs[i]))
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append((i, lows[i]))

        pattern = "no_pattern"
        confidence = 0.3

        # Double top: two similar swing highs
        if len(swing_highs) >= 2:
            last_two = swing_highs[-2:]
            price_diff = abs(last_two[0][1] - last_two[1][1])
            avg_price = (last_two[0][1] + last_two[1][1]) / 2
            if price_diff / avg_price < 0.01:  # Within 1%
                pattern = "double_top"
                confidence = 0.6

        # Double bottom: two similar swing lows
        if pattern == "no_pattern" and len(swing_lows) >= 2:
            last_two = swing_lows[-2:]
            price_diff = abs(last_two[0][1] - last_two[1][1])
            avg_price = (last_two[0][1] + last_two[1][1]) / 2
            if price_diff / avg_price < 0.01:
                pattern = "double_bottom"
                confidence = 0.6

        # Bull flag: strong up move followed by slight pullback
        if pattern == "no_pattern" and n > 20:
            first_half_change = (closes[mid] - closes[0]) / closes[0]
            second_half_change = (closes[-1] - closes[mid]) / closes[mid]
            if first_half_change > 0.02 and -0.01 < second_half_change < 0.005:
                pattern = "bull_flag"
                confidence = 0.55

        pattern_info = PATTERN_CATALOG.get(pattern, PATTERN_CATALOG["no_pattern"])

        return {
            "pattern": pattern,
            "confidence": round(confidence, 3),
            "direction": pattern_info.get("direction", "NEUTRAL"),
            "description": pattern_info.get("description", ""),
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "method": "rule_based",
        }
