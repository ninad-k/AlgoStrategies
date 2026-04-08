from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import Lock

from reyconnector.contracts import ConnectionSummary, IncomingAlertEnvelope


class InMemoryConnectionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[str, ConnectionSummary] = {}
        demo = ConnectionSummary(
            id="conn-demo-001",
            display_name="Demo MT5",
            is_enabled=True,
            created_at_utc=datetime.now(UTC),
            last_seen_at_utc=None,
        )
        self._by_id[demo.id] = demo

    def list_connections(self) -> list[ConnectionSummary]:
        with self._lock:
            return sorted(self._by_id.values(), key=lambda c: c.display_name)

    def get(self, cid: str) -> ConnectionSummary | None:
        with self._lock:
            return self._by_id.get(cid)


class InMemorySignalLogStore:
    def __init__(self, max_items: int = 500) -> None:
        self._lock = Lock()
        self._max = max_items
        self._q: deque[IncomingAlertEnvelope] = deque()

    def append(self, envelope: IncomingAlertEnvelope) -> None:
        with self._lock:
            self._q.append(envelope)
            while len(self._q) > self._max:
                self._q.popleft()

    def recent(self, take: int = 100) -> list[IncomingAlertEnvelope]:
        with self._lock:
            items = list(self._q)
        return list(reversed(items))[:take]


connection_store = InMemoryConnectionStore()
signal_log_store = InMemorySignalLogStore()
