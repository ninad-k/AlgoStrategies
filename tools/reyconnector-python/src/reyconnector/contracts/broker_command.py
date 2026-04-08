from typing import Literal

from reyconnector.contracts.base import CamelModel


class NoopCommand(CamelModel):
    kind: Literal["noop"] = "noop"
    reason: str
