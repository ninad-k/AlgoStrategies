from __future__ import annotations

from typing import Protocol, runtime_checkable

from teletrader.models.trading_signal import TradingSignal


@runtime_checkable
class SignalStoreProtocol(Protocol):
    """Abstract interface for signal storage backends."""

    def append(self, signal: TradingSignal) -> TradingSignal:
        """Store a signal and assign its sequence number. Returns the updated signal."""
        ...

    def since(self, seq: int) -> list[TradingSignal]:
        """Return all signals with seq > the given value, ordered by seq ascending."""
        ...

    def get(self, signal_id: str) -> TradingSignal | None:
        """Retrieve a signal by its ID."""
        ...
