from datetime import datetime

from reyconnector.contracts.base import CamelModel


class ConnectionSummary(CamelModel):
    id: str
    display_name: str
    is_enabled: bool
    created_at_utc: datetime
    last_seen_at_utc: datetime | None = None
