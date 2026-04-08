from __future__ import annotations

from typing import Protocol, runtime_checkable

from reyconnector.contracts import IncomingAlertEnvelope, NoopCommand


@runtime_checkable
class ExecutionEngineProtocol(Protocol):
    """Pluggable execution brain (Phase 6: partial TPs; swap implementation as needed)."""

    async def process(
        self,
        *,
        connection_id: str,
        alert: IncomingAlertEnvelope,
        metadata: dict[str, str] | None = None,
    ) -> list[NoopCommand]: ...


class DefaultExecutionEngine:
    async def process(
        self,
        *,
        connection_id: str,
        alert: IncomingAlertEnvelope,
        metadata: dict[str, str] | None = None,
    ) -> list[NoopCommand]:
        _ = (connection_id, alert, metadata)
        return [NoopCommand(reason="Phase 6: wire partial TP / trailing here")]
