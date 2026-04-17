"""Unit tests for the execution engine."""

from datetime import UTC, datetime

import pytest

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
from reyconnector.execution.engine import DefaultExecutionEngine


def _make_envelope(raw_body: str, connection_id: str = "conn-demo-001") -> IncomingAlertEnvelope:
    return IncomingAlertEnvelope.new(
        raw_body=raw_body,
        connection_id=connection_id,
        idempotency_key=None,
    )


def _make_connection(
    cid: str = "conn-demo-001",
    enabled: bool = True,
    lots: float = 0.10,
    magic: int = 100001,
    tp1_pct: float = 40.0,
    tp2_pct: float = 30.0,
    tp3_pct: float = 30.0,
    strategies: list[str] | None = None,
) -> ConnectionSummary:
    return ConnectionSummary(
        id=cid,
        display_name="Test",
        is_enabled=enabled,
        created_at_utc=datetime.now(UTC),
        config=ConnectionConfig(
            default_lots=lots,
            default_magic=magic,
            partial_tp=PartialTPConfig(
                tp1_close_percent=tp1_pct,
                tp2_close_percent=tp2_pct,
                tp3_close_percent=tp3_pct,
            ),
            enabled_strategies=strategies,
        ),
    )


class TestEngineBasicOrder:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_minimal_buy_order(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 1
        assert isinstance(cmds[0], MarketOrderCommand)
        assert cmds[0].symbol == "EURUSD"
        assert cmds[0].action == "buy"
        assert cmds[0].lots == 0.10  # from connection config
        assert cmds[0].magic == 100001

    async def test_minimal_sell_order(self, engine):
        envelope = _make_envelope("ema200,sell,XAUUSD")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 1
        assert isinstance(cmds[0], MarketOrderCommand)
        assert cmds[0].action == "sell"
        assert cmds[0].symbol == "XAUUSD"

    async def test_lots_from_alert_overrides_config(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,lots=0.50")
        conn = _make_connection(lots=0.10)
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert cmds[0].lots == 0.50

    async def test_stop_loss_forwarded(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,sl=1.0800")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert cmds[0].stop_loss == 1.0800

    async def test_no_connection_uses_defaults(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD")
        cmds = await engine.process(connection_id="unknown", alert=envelope, connection=None)

        assert len(cmds) == 1
        assert cmds[0].lots == 0.10  # hardcoded default
        assert cmds[0].magic == 0

    async def test_comment_includes_strategy_and_connection(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert "ema200" in cmds[0].comment
        assert "conn-demo-001" in cmds[0].comment


class TestEnginePartialProfit:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_single_tp_generates_market_order_and_partial_close(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 2
        assert isinstance(cmds[0], MarketOrderCommand)
        assert cmds[0].take_profit == 1.0900
        assert isinstance(cmds[1], PartialCloseCommand)
        assert cmds[1].trigger_price == 1.0900
        assert cmds[1].close_percent == 40.0  # from connection config tp1

    async def test_three_tps_generates_four_commands(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000,tp3=1.1100")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 4  # 1 market order + 3 partial closes
        assert isinstance(cmds[0], MarketOrderCommand)
        assert isinstance(cmds[1], PartialCloseCommand)
        assert isinstance(cmds[2], PartialCloseCommand)
        assert isinstance(cmds[3], PartialCloseCommand)

    async def test_tp_close_percents_from_connection_config(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000,tp3=1.1100")
        conn = _make_connection(tp1_pct=50.0, tp2_pct=25.0, tp3_pct=25.0)
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert cmds[1].close_percent == 50.0
        assert cmds[2].close_percent == 25.0
        assert cmds[3].close_percent == 25.0

    async def test_alert_close_percents_override_config(self, engine):
        envelope = _make_envelope(
            "ema200,buy,EURUSD,tp1=1.0900,close1=60,tp2=1.1000,close2=20,tp3=1.1100,close3=20"
        )
        conn = _make_connection(tp1_pct=40.0, tp2_pct=30.0, tp3_pct=30.0)
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert cmds[1].close_percent == 60.0
        assert cmds[2].close_percent == 20.0
        assert cmds[3].close_percent == 20.0

    async def test_market_order_tp_set_to_first_tp_level(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert cmds[0].take_profit == 1.0900

    async def test_partial_close_commands_have_correct_trigger_prices(self, engine):
        envelope = _make_envelope("ema200,sell,XAUUSD,tp1=2010,tp2=2000,tp3=1990")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert cmds[1].trigger_price == 2010.0
        assert cmds[2].trigger_price == 2000.0
        assert cmds[3].trigger_price == 1990.0

    async def test_partial_close_inherits_action_and_symbol(self, engine):
        envelope = _make_envelope("ema200,sell,GBPUSD,tp1=1.2600")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert cmds[1].symbol == "GBPUSD"
        assert cmds[1].action == "sell"

    async def test_partial_close_comments_describe_level(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert "tp1" in cmds[1].comment
        assert "tp2" in cmds[2].comment


class TestEngineTrailingStop:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_trailing_stop_command_generated(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,trailing=1.0950:0.0020")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        trailing_cmds = [c for c in cmds if isinstance(c, TrailingStopCommand)]
        assert len(trailing_cmds) == 1
        assert trailing_cmds[0].activation_price == 1.0950
        assert trailing_cmds[0].trailing_distance == 0.0020

    async def test_trailing_with_partials(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000,trailing=1.0950:0.002")
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        types = [type(c).__name__ for c in cmds]
        assert types == [
            "MarketOrderCommand",
            "PartialCloseCommand",
            "PartialCloseCommand",
            "TrailingStopCommand",
        ]


class TestEngineConnectionGuards:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_disabled_connection_returns_noop(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD")
        conn = _make_connection(enabled=False)
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 1
        assert isinstance(cmds[0], NoopCommand)
        assert "disabled" in cmds[0].reason

    async def test_strategy_not_in_enabled_list(self, engine):
        envelope = _make_envelope("goldFib,buy,EURUSD")
        conn = _make_connection(strategies=["ema200", "smartmoney"])
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 1
        assert isinstance(cmds[0], NoopCommand)
        assert "goldFib" in cmds[0].reason

    async def test_strategy_in_enabled_list_passes(self, engine):
        envelope = _make_envelope("ema200,buy,EURUSD")
        conn = _make_connection(strategies=["ema200", "smartmoney"])
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert isinstance(cmds[0], MarketOrderCommand)

    async def test_no_strategy_filter_allows_all(self, engine):
        envelope = _make_envelope("anyStrategy,buy,EURUSD")
        conn = _make_connection(strategies=None)
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert isinstance(cmds[0], MarketOrderCommand)


class TestEngineParseErrors:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_unparseable_alert_returns_noop(self, engine):
        envelope = _make_envelope("garbage")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert len(cmds) == 1
        assert isinstance(cmds[0], NoopCommand)
        assert "Parse error" in cmds[0].reason

    async def test_empty_body_returns_noop(self, engine):
        envelope = _make_envelope("")
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope)

        assert len(cmds) == 1
        assert isinstance(cmds[0], NoopCommand)


class TestEngineJSONAlerts:
    @pytest.fixture
    def engine(self):
        return DefaultExecutionEngine()

    async def test_json_alert_with_partial_tps(self, engine):
        raw = (
            '{"strategy":"ema200","action":"buy","symbol":"EURUSD",'
            '"sl":1.0800,"tp1":1.0900,"tp2":1.1000,"tp3":1.1100}'
        )
        envelope = _make_envelope(raw)
        conn = _make_connection()
        cmds = await engine.process(connection_id="conn-demo-001", alert=envelope, connection=conn)

        assert len(cmds) == 4
        assert isinstance(cmds[0], MarketOrderCommand)
        assert cmds[0].stop_loss == 1.0800
        assert cmds[1].trigger_price == 1.0900
        assert cmds[2].trigger_price == 1.1000
        assert cmds[3].trigger_price == 1.1100
