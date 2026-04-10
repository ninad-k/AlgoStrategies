"""Unit tests for data models and serialization."""

from datetime import UTC, datetime

from reyconnector.contracts import (
    ConnectionConfig,
    ConnectionSummary,
    IncomingAlertEnvelope,
    MarketOrderCommand,
    NoopCommand,
    PartialCloseCommand,
    PartialTPConfig,
    TrailingStopCommand,
)


# ── IncomingAlertEnvelope ────────────────────────────────────────────


class TestIncomingAlertEnvelope:
    def test_new_factory(self):
        env = IncomingAlertEnvelope.new(
            raw_body="ema200,buy,EURUSD",
            connection_id="conn-demo-001",
            idempotency_key="key-123",
        )
        assert len(env.id) == 32  # uuid4 hex
        assert env.connection_id == "conn-demo-001"
        assert env.raw_body == "ema200,buy,EURUSD"
        assert env.idempotency_key == "key-123"
        assert env.received_at_utc is not None

    def test_new_factory_optional_fields(self):
        env = IncomingAlertEnvelope.new(
            raw_body="test",
            connection_id=None,
            idempotency_key=None,
        )
        assert env.connection_id is None
        assert env.idempotency_key is None

    def test_camel_case_serialization(self):
        env = IncomingAlertEnvelope.new(
            raw_body="test",
            connection_id="conn-1",
            idempotency_key=None,
        )
        data = env.model_dump(mode="json", by_alias=True)
        assert "connectionId" in data
        assert "rawBody" in data
        assert "receivedAtUtc" in data
        assert "idempotencyKey" in data

    def test_camel_case_deserialization(self):
        env = IncomingAlertEnvelope.model_validate({
            "id": "abc123",
            "connectionId": "conn-1",
            "rawBody": "test",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        })
        assert env.connection_id == "conn-1"
        assert env.raw_body == "test"

    def test_snake_case_deserialization(self):
        env = IncomingAlertEnvelope.model_validate({
            "id": "abc123",
            "connection_id": "conn-1",
            "raw_body": "test",
            "received_at_utc": "2026-04-09T12:00:00Z",
        })
        assert env.connection_id == "conn-1"
        assert env.raw_body == "test"


# ── ConnectionSummary & Config ───────────────────────────────────────


class TestConnectionSummary:
    def test_defaults(self):
        conn = ConnectionSummary(
            id="conn-1",
            display_name="Test",
            is_enabled=True,
            created_at_utc=datetime.now(UTC),
        )
        assert conn.config.default_lots == 0.10
        assert conn.config.default_magic == 0
        assert conn.config.partial_tp.tp1_close_percent == 40.0
        assert conn.config.partial_tp.tp2_close_percent == 30.0
        assert conn.config.partial_tp.tp3_close_percent == 30.0
        assert conn.config.enabled_strategies is None

    def test_custom_config(self):
        conn = ConnectionSummary(
            id="conn-1",
            display_name="Live",
            is_enabled=True,
            created_at_utc=datetime.now(UTC),
            config=ConnectionConfig(
                default_lots=0.50,
                default_magic=999,
                partial_tp=PartialTPConfig(
                    tp1_close_percent=50.0,
                    tp2_close_percent=25.0,
                    tp3_close_percent=25.0,
                ),
                enabled_strategies=["ema200", "smartmoney"],
            ),
        )
        assert conn.config.default_lots == 0.50
        assert conn.config.partial_tp.tp1_close_percent == 50.0
        assert conn.config.enabled_strategies == ["ema200", "smartmoney"]

    def test_camel_serialization(self):
        conn = ConnectionSummary(
            id="conn-1",
            display_name="Test",
            is_enabled=True,
            created_at_utc=datetime.now(UTC),
        )
        data = conn.model_dump(mode="json", by_alias=True)
        assert "displayName" in data
        assert "isEnabled" in data
        assert "createdAtUtc" in data
        assert "config" in data
        assert "defaultLots" in data["config"]
        assert "partialTp" in data["config"]


# ── Broker Commands ──────────────────────────────────────────────────


class TestBrokerCommands:
    def test_noop_command(self):
        cmd = NoopCommand(reason="test")
        assert cmd.kind == "noop"
        assert cmd.reason == "test"

    def test_market_order_command(self):
        cmd = MarketOrderCommand(
            symbol="EURUSD",
            action="buy",
            lots=0.10,
            stop_loss=1.0800,
            take_profit=1.0900,
            magic=100001,
            comment="test",
        )
        assert cmd.kind == "market_order"
        assert cmd.symbol == "EURUSD"
        assert cmd.action == "buy"
        assert cmd.lots == 0.10

    def test_market_order_defaults(self):
        cmd = MarketOrderCommand(symbol="EURUSD", action="buy", lots=0.10)
        assert cmd.stop_loss is None
        assert cmd.take_profit is None
        assert cmd.magic == 0
        assert cmd.comment == ""

    def test_partial_close_command(self):
        cmd = PartialCloseCommand(
            symbol="EURUSD",
            action="buy",
            close_percent=40.0,
            trigger_price=1.0900,
            magic=100001,
            comment="tp1:40%",
        )
        assert cmd.kind == "partial_close"
        assert cmd.close_percent == 40.0
        assert cmd.trigger_price == 1.0900

    def test_trailing_stop_command(self):
        cmd = TrailingStopCommand(
            symbol="EURUSD",
            action="buy",
            activation_price=1.0950,
            trailing_distance=0.0020,
        )
        assert cmd.kind == "trailing_stop"
        assert cmd.activation_price == 1.0950
        assert cmd.trailing_distance == 0.0020

    def test_camel_serialization_market_order(self):
        cmd = MarketOrderCommand(
            symbol="EURUSD",
            action="buy",
            lots=0.10,
            stop_loss=1.0800,
            take_profit=1.0900,
        )
        data = cmd.model_dump(mode="json", by_alias=True)
        assert "stopLoss" in data
        assert "takeProfit" in data
        assert data["stopLoss"] == 1.0800

    def test_camel_serialization_partial_close(self):
        cmd = PartialCloseCommand(
            symbol="EURUSD",
            action="buy",
            close_percent=40.0,
            trigger_price=1.0900,
        )
        data = cmd.model_dump(mode="json", by_alias=True)
        assert "closePercent" in data
        assert "triggerPrice" in data

    def test_camel_serialization_trailing(self):
        cmd = TrailingStopCommand(
            symbol="EURUSD",
            action="buy",
            activation_price=1.0950,
            trailing_distance=0.0020,
        )
        data = cmd.model_dump(mode="json", by_alias=True)
        assert "activationPrice" in data
        assert "trailingDistance" in data
