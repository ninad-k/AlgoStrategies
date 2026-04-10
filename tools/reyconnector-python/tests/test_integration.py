"""Integration tests: full webhook -> control API -> execution engine pipeline.

Uses FastAPI TestClient (HTTPX-backed) to test actual HTTP round-trips
through the real application stack without spawning separate processes.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from reyconnector.application.stores import (
    InMemoryConnectionStore,
    InMemorySignalLogStore,
)
from reyconnector.contracts import ConnectionConfig, ConnectionSummary, PartialTPConfig


# ── Control API integration tests ────────────────────────────────────


@pytest.fixture
def _reset_control_api_stores():
    """Reset singleton stores before each test."""
    import reyconnector.application.stores as store_mod
    import reyconnector.apps.control_api as api_mod

    original_conn = store_mod.connection_store
    original_sig = store_mod.signal_log_store

    fresh_conn = InMemoryConnectionStore()
    fresh_sig = InMemorySignalLogStore()

    store_mod.connection_store = fresh_conn
    store_mod.signal_log_store = fresh_sig
    api_mod.connection_store = fresh_conn
    api_mod.signal_log_store = fresh_sig

    yield fresh_conn, fresh_sig

    store_mod.connection_store = original_conn
    store_mod.signal_log_store = original_sig
    api_mod.connection_store = original_conn
    api_mod.signal_log_store = original_sig


class TestControlAPIHealth:
    def test_health(self):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "reyconnector.control_api"


class TestControlAPIConnections:
    def test_list_connections_returns_demo(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        resp = client.get("/api/v1/connections")
        assert resp.status_code == 200
        conns = resp.json()
        assert len(conns) == 1
        assert conns[0]["id"] == "conn-demo-001"
        assert conns[0]["displayName"] == "Demo MT5"
        assert "config" in conns[0]


class TestControlAPISignalIngest:
    def test_ingest_minimal_signal(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-001",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["id"] == "test-signal-001"
        assert "commands" in data
        assert len(data["commands"]) >= 1

    def test_ingest_returns_market_order_command(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-002",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD,sl=1.0800,tp1=1.0900",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        cmds = data["commands"]

        market_order = cmds[0]
        assert market_order["kind"] == "market_order"
        assert market_order["symbol"] == "EURUSD"
        assert market_order["action"] == "buy"
        assert market_order["stopLoss"] == 1.0800
        assert market_order["takeProfit"] == 1.0900

    def test_ingest_returns_partial_close_commands(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-003",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD,tp1=1.0900,tp2=1.1000,tp3=1.1100",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        assert len(cmds) == 4  # market order + 3 partial closes
        assert cmds[0]["kind"] == "market_order"
        assert cmds[1]["kind"] == "partial_close"
        assert cmds[2]["kind"] == "partial_close"
        assert cmds[3]["kind"] == "partial_close"

        assert cmds[1]["triggerPrice"] == 1.0900
        assert cmds[2]["triggerPrice"] == 1.1000
        assert cmds[3]["triggerPrice"] == 1.1100

    def test_ingest_with_trailing_stop(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-004",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD,tp1=1.09,trailing=1.0950:0.0020",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        kinds = [c["kind"] for c in cmds]
        assert "trailing_stop" in kinds
        trailing = next(c for c in cmds if c["kind"] == "trailing_stop")
        assert trailing["activationPrice"] == 1.0950
        assert trailing["trailingDistance"] == 0.0020

    def test_ingest_unparseable_returns_noop(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-005",
            "connectionId": "conn-demo-001",
            "rawBody": "garbage",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        assert len(cmds) == 1
        assert cmds[0]["kind"] == "noop"
        assert "Parse error" in cmds[0]["reason"]

    def test_ingest_signal_appears_in_log(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-006",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        client.post("/api/internal/v1/signals", json=payload)

        resp = client.get("/api/v1/signals")
        signals = resp.json()
        assert len(signals) == 1
        assert signals[0]["id"] == "test-signal-006"
        assert signals[0]["rawBody"] == "ema200,buy,EURUSD"

    def test_ingest_json_alert_body(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        json_body = json.dumps({
            "strategy": "goldFib",
            "action": "sell",
            "symbol": "XAUUSD",
            "sl": 2050.00,
            "tp1": 2030.00,
            "tp2": 2010.00,
            "tp3": 1990.00,
        })
        payload = {
            "id": "test-signal-007",
            "connectionId": "conn-demo-001",
            "rawBody": json_body,
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        assert cmds[0]["kind"] == "market_order"
        assert cmds[0]["symbol"] == "XAUUSD"
        assert cmds[0]["action"] == "sell"
        assert cmds[0]["stopLoss"] == 2050.00
        assert len(cmds) == 4  # market order + 3 partials

    def test_ingest_with_custom_close_percents(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "test-signal-008",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD,tp1=1.09,close1=60,tp2=1.10,close2=25,tp3=1.11,close3=15",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        partials = [c for c in cmds if c["kind"] == "partial_close"]
        assert partials[0]["closePercent"] == 60.0
        assert partials[1]["closePercent"] == 25.0
        assert partials[2]["closePercent"] == 15.0

    def test_ingest_uses_connection_config_lots(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        conn_store, _ = _reset_control_api_stores
        client = TestClient(app)

        # Demo connection has default_lots=0.10, default_magic=100001
        payload = {
            "id": "test-signal-009",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        assert cmds[0]["lots"] == 0.10
        assert cmds[0]["magic"] == 100001


# ── Webhook Ingest integration tests ────────────────────────────────


class TestWebhookIngestHealth:
    def test_health(self):
        from reyconnector.apps.webhook_ingest import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "reyconnector.webhook_ingest"


class TestWebhookIngestPipeline:
    def test_webhook_creates_envelope_and_forwards(self):
        """Test the full webhook -> forward to control API flow using a mock."""
        from reyconnector.apps.webhook_ingest import app

        mock_response = AsyncMock()
        mock_response.status_code = 202
        mock_response.text = '{"id": "test"}'

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app)
            resp = client.post(
                "/v1/webhook?connection_id=conn-demo-001",
                content="ema200,buy,EURUSD",
                headers={"Content-Type": "text/plain"},
            )

            assert resp.status_code == 202
            data = resp.json()
            assert "signalId" in data
            assert "receivedAtUtc" in data

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            forwarded_body = call_args.kwargs.get("json") or call_args[1].get("json")
            assert forwarded_body["rawBody"] == "ema200,buy,EURUSD"
            assert forwarded_body["connectionId"] == "conn-demo-001"

    def test_webhook_camel_case_connection_id(self):
        """Test that connectionId query param works (camelCase)."""
        from reyconnector.apps.webhook_ingest import app

        mock_response = AsyncMock()
        mock_response.status_code = 202

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app)
            resp = client.post(
                "/v1/webhook?connectionId=conn-live-001",
                content="ema200,buy,EURUSD",
            )

            assert resp.status_code == 202
            forwarded = mock_client.post.call_args.kwargs.get("json") or \
                mock_client.post.call_args[1].get("json")
            assert forwarded["connectionId"] == "conn-live-001"

    def test_webhook_idempotency_key_forwarded(self):
        """Test that X-Idempotency-Key header is captured."""
        from reyconnector.apps.webhook_ingest import app

        mock_response = AsyncMock()
        mock_response.status_code = 202

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app)
            resp = client.post(
                "/v1/webhook?connection_id=conn-demo-001",
                content="test",
                headers={"X-Idempotency-Key": "idem-key-123"},
            )

            assert resp.status_code == 202
            forwarded = mock_client.post.call_args.kwargs.get("json") or \
                mock_client.post.call_args[1].get("json")
            assert forwarded["idempotencyKey"] == "idem-key-123"

    def test_webhook_returns_503_on_network_error(self):
        """Test that webhook returns 503 when Control API is unreachable."""
        from reyconnector.apps.webhook_ingest import app

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = ConnectionError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/webhook?connection_id=conn-demo-001",
                content="ema200,buy,EURUSD",
            )

            assert resp.status_code == 503
            data = resp.json()
            assert "forwarding failed" in data["detail"]
            assert "Connection refused" in data["error"]

    def test_webhook_with_partial_profit_csv(self):
        """End-to-end: CSV alert with partial TPs forwarded correctly."""
        from reyconnector.apps.webhook_ingest import app

        mock_response = AsyncMock()
        mock_response.status_code = 202

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app)
            raw = "ema200,buy,EURUSD,sl=1.0800,tp1=1.0900,tp2=1.1000,tp3=1.1100"
            resp = client.post(
                "/v1/webhook?connection_id=conn-demo-001",
                content=raw,
            )

            assert resp.status_code == 202
            forwarded = mock_client.post.call_args.kwargs.get("json") or \
                mock_client.post.call_args[1].get("json")
            assert forwarded["rawBody"] == raw

    def test_webhook_with_json_alert_body(self):
        """End-to-end: JSON alert body forwarded correctly."""
        from reyconnector.apps.webhook_ingest import app

        mock_response = AsyncMock()
        mock_response.status_code = 202

        with patch("reyconnector.apps.webhook_ingest.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            client = TestClient(app)
            raw = json.dumps({
                "strategy": "ema200",
                "action": "buy",
                "symbol": "EURUSD",
                "tp1": 1.09,
                "tp2": 1.10,
            })
            resp = client.post(
                "/v1/webhook?connection_id=conn-demo-001",
                content=raw,
                headers={"Content-Type": "application/json"},
            )

            assert resp.status_code == 202


# ── Gateway integration tests ────────────────────────────────────────


class TestGateway:
    def test_health(self):
        from reyconnector.apps.gateway import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_info(self):
        from reyconnector.apps.gateway import app

        client = TestClient(app)
        resp = client.get("/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product"] == "ReyConnector"
        assert data["stack"] == "python"


# ── Full pipeline integration test ───────────────────────────────────


class TestFullPipeline:
    """Test the complete flow: signal ingest -> execution engine -> commands.

    These tests use the Control API TestClient directly (skipping the webhook
    hop) to test the ingest + execution pipeline as a single unit.
    """

    def test_buy_eurusd_with_3_partial_tps_and_trailing(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "pipeline-001",
            "connectionId": "conn-demo-001",
            "rawBody": (
                "smartmoney,buy,EURUSD,lots=0.20,sl=1.0750,"
                "tp1=1.0900,close1=50,tp2=1.1000,close2=30,tp3=1.1100,close3=20,"
                "trailing=1.0950:0.0020,magic=200,comment=smc_entry"
            ),
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        assert resp.status_code == 202
        data = resp.json()

        cmds = data["commands"]
        assert len(cmds) == 5  # market + 3 partials + trailing

        # Market order
        mo = cmds[0]
        assert mo["kind"] == "market_order"
        assert mo["symbol"] == "EURUSD"
        assert mo["action"] == "buy"
        assert mo["lots"] == 0.20
        assert mo["stopLoss"] == 1.0750
        assert mo["takeProfit"] == 1.0900
        assert mo["magic"] == 200
        assert mo["comment"] == "smc_entry"

        # Partial closes
        p1 = cmds[1]
        assert p1["kind"] == "partial_close"
        assert p1["triggerPrice"] == 1.0900
        assert p1["closePercent"] == 50.0
        assert p1["symbol"] == "EURUSD"
        assert p1["action"] == "buy"

        p2 = cmds[2]
        assert p2["triggerPrice"] == 1.1000
        assert p2["closePercent"] == 30.0

        p3 = cmds[3]
        assert p3["triggerPrice"] == 1.1100
        assert p3["closePercent"] == 20.0

        # Trailing stop
        ts = cmds[4]
        assert ts["kind"] == "trailing_stop"
        assert ts["activationPrice"] == 1.0950
        assert ts["trailingDistance"] == 0.0020
        assert ts["magic"] == 200

    def test_sell_xauusd_defaults_from_connection(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "pipeline-002",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,sell,XAUUSD,tp1=2010,tp2=2000,tp3=1990",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        # Lots and magic from connection config defaults
        assert cmds[0]["lots"] == 0.10
        assert cmds[0]["magic"] == 100001

        # Close percents from connection config (40/30/30)
        partials = [c for c in cmds if c["kind"] == "partial_close"]
        assert partials[0]["closePercent"] == 40.0
        assert partials[1]["closePercent"] == 30.0
        assert partials[2]["closePercent"] == 30.0

    def test_signal_persisted_after_execution(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "pipeline-003",
            "connectionId": "conn-demo-001",
            "rawBody": "ema200,buy,EURUSD",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        client.post("/api/internal/v1/signals", json=payload)

        signals = client.get("/api/v1/signals").json()
        assert len(signals) == 1
        assert signals[0]["id"] == "pipeline-003"

    def test_multiple_signals_ordered_newest_first(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        for i in range(5):
            payload = {
                "id": f"pipeline-multi-{i}",
                "connectionId": "conn-demo-001",
                "rawBody": f"ema200,buy,EURUSD,tp1=1.{i:04d}",
                "receivedAtUtc": f"2026-04-09T12:0{i}:00Z",
            }
            client.post("/api/internal/v1/signals", json=payload)

        signals = client.get("/api/v1/signals").json()
        assert len(signals) == 5
        assert signals[0]["id"] == "pipeline-multi-4"  # newest first

    def test_unknown_connection_still_produces_commands(self, _reset_control_api_stores):
        from reyconnector.apps.control_api import app

        client = TestClient(app)
        payload = {
            "id": "pipeline-unknown",
            "connectionId": "nonexistent-connection",
            "rawBody": "ema200,buy,EURUSD,tp1=1.0900",
            "receivedAtUtc": "2026-04-09T12:00:00Z",
        }
        resp = client.post("/api/internal/v1/signals", json=payload)
        data = resp.json()
        cmds = data["commands"]

        # Should still work with hardcoded defaults
        assert cmds[0]["kind"] == "market_order"
        assert cmds[0]["lots"] == 0.10  # hardcoded default
