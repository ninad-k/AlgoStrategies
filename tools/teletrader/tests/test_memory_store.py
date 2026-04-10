"""Tests for the in-memory signal store."""

from teletrader.models.trading_signal import TradingSignal
from teletrader.store.memory_store import InMemorySignalStore


def _make_signal(**kwargs) -> TradingSignal:
    defaults = {
        "symbol": "XAUUSD",
        "direction": "buy",
        "order_type": "buy_stop",
        "entry_price": 4756.0,
        "stop_loss": 4736.0,
        "take_profits": [4760.0, 4764.0, 4785.0],
        "raw_text": "test signal",
    }
    defaults.update(kwargs)
    return TradingSignal(**defaults)


class TestInMemorySignalStore:
    def test_append_assigns_seq(self):
        store = InMemorySignalStore()
        s1 = store.append(_make_signal())
        s2 = store.append(_make_signal())
        assert s1.seq == 1
        assert s2.seq == 2

    def test_since_returns_newer(self):
        store = InMemorySignalStore()
        store.append(_make_signal())
        store.append(_make_signal())
        s3 = store.append(_make_signal())

        result = store.since(1)
        assert len(result) == 2
        assert result[0].seq == 2
        assert result[1].seq == 3

    def test_since_zero_returns_all(self):
        store = InMemorySignalStore()
        store.append(_make_signal())
        store.append(_make_signal())
        assert len(store.since(0)) == 2

    def test_since_latest_returns_empty(self):
        store = InMemorySignalStore()
        store.append(_make_signal())
        store.append(_make_signal())
        assert len(store.since(2)) == 0

    def test_get_by_id(self):
        store = InMemorySignalStore()
        s1 = store.append(_make_signal())
        found = store.get(s1.signal_id)
        assert found is not None
        assert found.signal_id == s1.signal_id

    def test_get_missing_returns_none(self):
        store = InMemorySignalStore()
        assert store.get("nonexistent") is None

    def test_max_capacity_evicts_oldest(self):
        store = InMemorySignalStore(max_signals=3)
        store.append(_make_signal())  # seq=1
        store.append(_make_signal())  # seq=2
        store.append(_make_signal())  # seq=3
        store.append(_make_signal())  # seq=4, evicts seq=1

        result = store.since(0)
        assert len(result) == 3
        assert result[0].seq == 2  # seq=1 was evicted
