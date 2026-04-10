from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from reyconnector.contracts import (
    BrokerCommand,
    ConnectionSummary,
    IncomingAlertEnvelope,
    MarketOrderCommand,
    NoopCommand,
    PartialCloseCommand,
    TrailingStopCommand,
)
from reyconnector.execution.parser import AlertParseError, ParsedAlert, parse_alert

log = logging.getLogger(__name__)


@runtime_checkable
class ExecutionEngineProtocol(Protocol):
    """Pluggable execution brain — processes alerts into broker commands."""

    async def process(
        self,
        *,
        connection_id: str,
        alert: IncomingAlertEnvelope,
        connection: ConnectionSummary | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[BrokerCommand]: ...


class DefaultExecutionEngine:
    """Execution engine that parses alerts and generates partial-profit broker commands.

    Flow:
      1. Parse ``alert.raw_body`` into a ``ParsedAlert``
      2. Resolve lots (alert override > connection default)
      3. Generate a ``MarketOrderCommand`` with SL and first TP
      4. Generate ``PartialCloseCommand`` for each TP level
      5. Optionally generate ``TrailingStopCommand``
    """

    async def process(
        self,
        *,
        connection_id: str,
        alert: IncomingAlertEnvelope,
        connection: ConnectionSummary | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[BrokerCommand]:
        try:
            parsed = parse_alert(alert.raw_body)
        except AlertParseError as exc:
            log.warning("Cannot parse alert %s: %s", alert.id, exc)
            return [NoopCommand(reason=f"Parse error: {exc}")]

        if connection and not connection.is_enabled:
            return [NoopCommand(reason=f"Connection {connection_id} is disabled")]

        if connection and connection.config.enabled_strategies:
            if parsed.strategy not in connection.config.enabled_strategies:
                return [
                    NoopCommand(
                        reason=(
                            f"Strategy '{parsed.strategy}' not in enabled list "
                            f"for {connection_id}"
                        )
                    )
                ]

        return self._build_commands(parsed, connection, connection_id)

    def _build_commands(
        self,
        parsed: ParsedAlert,
        connection: ConnectionSummary | None,
        connection_id: str,
    ) -> list[BrokerCommand]:
        cfg = connection.config if connection else None
        lots = parsed.lots or (cfg.default_lots if cfg else 0.10)
        magic = parsed.magic or (cfg.default_magic if cfg else 0)

        commands: list[BrokerCommand] = []

        first_tp = parsed.partial_tps[0].price if parsed.partial_tps else None
        commands.append(
            MarketOrderCommand(
                symbol=parsed.symbol,
                action=parsed.action,
                lots=lots,
                stop_loss=parsed.stop_loss,
                take_profit=first_tp,
                magic=magic,
                comment=parsed.comment or f"rey:{parsed.strategy}:{connection_id}",
            )
        )

        if parsed.partial_tps:
            tp_defaults = cfg.partial_tp if cfg else None
            default_pcts = {
                1: tp_defaults.tp1_close_percent if tp_defaults else 40.0,
                2: tp_defaults.tp2_close_percent if tp_defaults else 30.0,
                3: tp_defaults.tp3_close_percent if tp_defaults else 30.0,
            }

            for tp in parsed.partial_tps:
                pct = tp.close_percent if tp.close_percent is not None else default_pcts.get(
                    tp.level, 100.0 / len(parsed.partial_tps)
                )
                commands.append(
                    PartialCloseCommand(
                        symbol=parsed.symbol,
                        action=parsed.action,
                        close_percent=pct,
                        trigger_price=tp.price,
                        magic=magic,
                        comment=f"tp{tp.level}:{pct}%",
                    )
                )

        if parsed.trailing:
            commands.append(
                TrailingStopCommand(
                    symbol=parsed.symbol,
                    action=parsed.action,
                    activation_price=parsed.trailing.activation_price,
                    trailing_distance=parsed.trailing.trailing_distance,
                    magic=magic,
                )
            )

        return commands
