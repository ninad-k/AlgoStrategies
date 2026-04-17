from __future__ import annotations

import threading

from teletrader.models.trading_signal import TradingSignal


class InMemorySignalStore:
    """Thread-safe in-memory signal store with auto-incrementing sequence IDs.

    Suitable for local development. For production, use DynamoDBSignalStore.
    """

    def __init__(self, max_signals: int = 500) -> None:
        self._lock = threading.Lock()
        self._seq_counter = 0
        self._signals: dict[int, TradingSignal] = {}
        self._max_signals = max_signals

    def append(self, signal: TradingSignal) -> TradingSignal:
        with self._lock:
            self._seq_counter += 1
            signal.seq = self._seq_counter

            self._signals[self._seq_counter] = signal

            # Evict oldest if over capacity
            if len(self._signals) > self._max_signals:
                oldest_key = min(self._signals)
                del self._signals[oldest_key]

            return signal

    def since(self, seq: int) -> list[TradingSignal]:
        with self._lock:
            return [
                s for s_seq, s in sorted(self._signals.items())
                if s_seq > seq
            ]

    def get(self, signal_id: str) -> TradingSignal | None:
        with self._lock:
            for s in self._signals.values():
                if s.signal_id == signal_id:
                    return s
            return None
