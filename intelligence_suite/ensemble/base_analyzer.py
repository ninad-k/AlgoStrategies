"""
Base Analyzer — Abstract interface for all trading models.
Every model adapter must implement this interface so the
ensemble engine can call them uniformly.
"""

from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    """
    Abstract base for trading signal analyzers.
    Each implementation wraps a specific model (LLM, ONNX, etc.)
    and returns a standardized decision dict.
    """

    name: str = "base"

    @abstractmethod
    def analyze(self, market_data: dict, config: dict) -> dict:
        """
        Analyze market data and return a trade decision.

        Args:
            market_data: Dict with 30+ indicator values from shared.indicators.
            config: Full suite config dict.

        Returns:
            Dict with keys:
                action: "BUY" | "SELL" | "HOLD"
                confidence: float 0.0–1.0
                sl_distance_atr: float
                tp_distance_atr: float
                reason: str
                model_name: str
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model backend is reachable."""
        pass
