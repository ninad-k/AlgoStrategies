"""Unit tests for in-memory stores."""

from datetime import UTC, datetime

from reyconnector.application.stores import InMemoryConnectionStore, InMemorySignalLogStore
from reyconnector.contracts import ConnectionConfig, ConnectionSummary, IncomingAlertEnvelope


class TestConnectionStore:
    def test_demo_connection_preloaded(self):
        store = InMemoryConnectionStore()
        conns = store.list_connections()
        assert len(conns) == 1
        assert conns[0].id == "conn-demo-001"
        assert conns[0].display_name == "Demo MT5"
        assert conns[0].is_enabled is True

    def test_get_existing(self):
        store = InMemoryConnectionStore()
        conn = store.get("conn-demo-001")
        assert conn is not None
        assert conn.id == "conn-demo-001"

    def test_get_missing(self):
        store = InMemoryConnectionStore()
        conn = store.get("nonexistent")
        assert conn is None

    def test_upsert_new(self):
        store = InMemoryConnectionStore()
        new_conn = ConnectionSummary(
            id="conn-live-001",
            display_name="Live Account",
            is_enabled=True,
            created_at_utc=datetime.now(UTC),
            config=ConnectionConfig(default_lots=0.50),
        )
        store.upsert(new_conn)

        result = store.get("conn-live-001")
        assert result is not None
        assert result.display_name == "Live Account"
        assert result.config.default_lots == 0.50

    def test_upsert_overwrite(self):
        store = InMemoryConnectionStore()
        updated = ConnectionSummary(
            id="conn-demo-001",
            display_name="Updated Demo",
            is_enabled=False,
            created_at_utc=datetime.now(UTC),
        )
        store.upsert(updated)

        result = store.get("conn-demo-001")
        assert result is not None
        assert result.display_name == "Updated Demo"
        assert result.is_enabled is False

    def test_list_sorted_by_display_name(self):
        store = InMemoryConnectionStore()
        store.upsert(
            ConnectionSummary(
                id="conn-z",
                display_name="Zulu",
                is_enabled=True,
                created_at_utc=datetime.now(UTC),
            )
        )
        store.upsert(
            ConnectionSummary(
                id="conn-a",
                display_name="Alpha",
                is_enabled=True,
                created_at_utc=datetime.now(UTC),
            )
        )
        conns = store.list_connections()
        names = [c.display_name for c in conns]
        assert names == sorted(names)


class TestSignalLogStore:
    def _make_envelope(self, body: str = "test") -> IncomingAlertEnvelope:
        return IncomingAlertEnvelope.new(
            raw_body=body,
            connection_id="conn-1",
            idempotency_key=None,
        )

    def test_empty_store(self):
        store = InMemorySignalLogStore()
        assert store.recent() == []

    def test_append_and_recent(self):
        store = InMemorySignalLogStore()
        env1 = self._make_envelope("first")
        env2 = self._make_envelope("second")
        store.append(env1)
        store.append(env2)

        result = store.recent()
        assert len(result) == 2
        assert result[0].raw_body == "second"  # newest first
        assert result[1].raw_body == "first"

    def test_take_parameter(self):
        store = InMemorySignalLogStore()
        for i in range(10):
            store.append(self._make_envelope(f"msg-{i}"))

        result = store.recent(take=3)
        assert len(result) == 3
        assert result[0].raw_body == "msg-9"

    def test_eviction_at_max(self):
        store = InMemorySignalLogStore(max_items=5)
        for i in range(10):
            store.append(self._make_envelope(f"msg-{i}"))

        result = store.recent(take=10)
        assert len(result) == 5
        assert result[0].raw_body == "msg-9"
        assert result[4].raw_body == "msg-5"

    def test_recent_reverse_chronological(self):
        store = InMemorySignalLogStore()
        for i in range(5):
            store.append(self._make_envelope(f"msg-{i}"))

        result = store.recent()
        bodies = [r.raw_body for r in result]
        assert bodies == ["msg-4", "msg-3", "msg-2", "msg-1", "msg-0"]
