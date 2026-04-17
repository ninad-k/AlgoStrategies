import uuid
from datetime import UTC, datetime

from reyconnector.contracts.base import CamelModel


class IncomingAlertEnvelope(CamelModel):
    id: str
    connection_id: str | None = None
    raw_body: str
    idempotency_key: str | None = None
    received_at_utc: datetime

    @staticmethod
    def new(
        *,
        raw_body: str,
        connection_id: str | None,
        idempotency_key: str | None,
    ) -> "IncomingAlertEnvelope":
        return IncomingAlertEnvelope(
            id=uuid.uuid4().hex,
            connection_id=connection_id,
            raw_body=raw_body,
            idempotency_key=idempotency_key,
            received_at_utc=datetime.now(UTC),
        )
