"""PineConnector FastAPI application — webhook receiver and API."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, database
from .models import (
    ExecutionResult,
    HealthResponse,
    StateUpdate,
    ValidatedSignal,
)
from .parser import parse_alert

log = logging.getLogger(__name__)

app = FastAPI(title="PineConnector", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_DIR = Path(__file__).parent.parent / "client"

_start_time: float = 0.0
_zmq_producer = None  # set in startup
_zmq_result_consumer = None
_zmq_state_subscriber = None
_risk_manager = None  # set in startup
_notifier = None
_mt5_bridge = None
_symbol_map: dict[str, str] = {}
_pip_sizes: dict[str, float] = {}


@app.on_event("startup")
async def startup() -> None:
    global _start_time, _zmq_producer, _zmq_result_consumer
    global _zmq_state_subscriber, _risk_manager, _notifier
    global _mt5_bridge, _symbol_map, _pip_sizes

    _start_time = time.time()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Init database
    database.init_db()

    # Load symbol map
    _load_symbols()

    # Init risk manager
    from .risk import RiskManager

    _risk_manager = RiskManager()

    # Init ZMQ producer
    from .queue import ZMQProducer, ZMQConsumer, ZMQStateSubscriber

    _zmq_producer = ZMQProducer(config.ZMQ_SIGNAL_ADDR)
    _zmq_result_consumer = ZMQConsumer(config.ZMQ_RESULT_ADDR)
    _zmq_state_subscriber = ZMQStateSubscriber(config.ZMQ_STATE_ADDR)

    # Init notifier
    from .notifications import TelegramNotifier

    _notifier = TelegramNotifier()

    # Start MT5 bridge if Python mode
    if config.MT5_BRIDGE_MODE == "python" and not config.DRY_RUN:
        from .mt5_bridge import MT5Bridge

        _mt5_bridge = MT5Bridge()
        _mt5_bridge.start()
        log.info("MT5 Python bridge started")

    # Start background result consumer
    asyncio.create_task(_consume_results())
    asyncio.create_task(_consume_state_updates())

    mode = "DRY RUN" if config.DRY_RUN else "LIVE"
    auth = "ENABLED" if config.WEBHOOK_TOKEN else "DISABLED (no token set)"
    log.info(
        "PineConnector started | Mode: %s | Auth: %s | Bridge: %s | Port: %d",
        mode,
        auth,
        config.MT5_BRIDGE_MODE,
        config.PORT,
    )


def _load_symbols() -> None:
    global _symbol_map, _pip_sizes
    import yaml

    symbols_path = Path(__file__).parent.parent / "configs" / "symbols.yaml"
    if symbols_path.exists():
        with open(symbols_path) as f:
            data = yaml.safe_load(f) or {}
        _symbol_map = data.get("mapping", {})
        _pip_sizes = data.get("pip_sizes", {})
        log.info("Loaded %d symbol mappings", len(_symbol_map))
    else:
        log.warning("No symbols.yaml found, using passthrough mapping")


def _authenticate(request: Request, alert_token: str = "") -> None:
    if not config.WEBHOOK_TOKEN:
        return
    token = (
        request.headers.get("X-Auth-Token", "")
        or request.query_params.get("token", "")
        or alert_token
    )
    if token != config.WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


def _map_symbol(tv_symbol: str) -> str:
    return _symbol_map.get(tv_symbol, _symbol_map.get(tv_symbol.upper(), tv_symbol))


# ─── Webhook ─────────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    body = await request.body()
    content_type = request.headers.get("content-type", "application/json")

    # Parse
    try:
        alert = parse_alert(body, content_type)
    except Exception as e:
        log.warning("Parse error: %s | body: %s", e, body[:200])
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    # Authenticate
    _authenticate(request, alert.token)

    now = datetime.now(timezone.utc)
    tv_symbol = alert.symbol
    mt5_symbol = _map_symbol(tv_symbol)

    # Risk check
    passed, reason = await _risk_manager.check(alert, mt5_symbol)

    signal_id = ""
    if passed:
        signal = ValidatedSignal(
            action=alert.action,
            symbol=mt5_symbol,
            tv_symbol=tv_symbol,
            lot=alert.lot,
            sl=alert.sl,
            tp=alert.tp,
            sl_pips=alert.sl_pips,
            tp_pips=alert.tp_pips,
            price=alert.price,
            comment=alert.comment or f"PC_{alert.action.value}",
            magic=alert.magic,
            partial_tp=alert.partial_tp,
            trailing=alert.trailing,
            time_exit_minutes=alert.time_exit_minutes,
            risk_percent=alert.risk_percent,
            dry_run=config.DRY_RUN,
        )
        signal_id = signal.signal_id

        # Save to DB (non-blocking)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            database.save_signal,
            signal_id,
            body.decode("utf-8", errors="replace"),
            alert.action.value,
            mt5_symbol,
            alert.lot,
            alert.sl,
            alert.tp,
            True,
            "",
            config.DRY_RUN,
            now.isoformat(),
        )

        # Push to Rust engine via ZMQ
        await _zmq_producer.send(signal)
        log.info("Signal dispatched: %s %s %s lot=%.2f", signal_id, alert.action.value, mt5_symbol, alert.lot)
    else:
        # Save rejected signal
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            database.save_signal,
            ValidatedSignal(action=alert.action, symbol=mt5_symbol).signal_id,
            body.decode("utf-8", errors="replace"),
            alert.action.value,
            mt5_symbol,
            alert.lot,
            alert.sl,
            alert.tp,
            False,
            reason,
            config.DRY_RUN,
            now.isoformat(),
        )
        log.info("Signal rejected: %s %s — %s", alert.action.value, mt5_symbol, reason)

    return JSONResponse(
        content={
            "status": "accepted" if passed else "rejected",
            "signal_id": signal_id,
            "reason": reason,
        }
    )


# ─── Background consumers ────────────────────────────────────────────

async def _consume_results() -> None:
    """Consume execution results from MT5 bridge."""
    while True:
        try:
            data = await _zmq_result_consumer.receive()
            if data is None:
                await asyncio.sleep(0.01)
                continue
            result = ExecutionResult(**data)
            log.info(
                "Result: cmd=%s signal=%s success=%s ticket=%d",
                result.command_id,
                result.signal_id,
                result.success,
                result.ticket,
            )

            # Update trade in DB
            loop = asyncio.get_event_loop()
            if result.success:
                await loop.run_in_executor(
                    None,
                    database.update_trade,
                    result.signal_id,
                    **{
                        "ticket": result.ticket,
                        "entry_price": result.executed_price,
                        "status": "open",
                    },
                )
                if _notifier:
                    await _notifier.notify_trade_opened(result)
            else:
                await loop.run_in_executor(
                    None,
                    database.update_trade,
                    result.signal_id,
                    **{"status": "error"},
                )
                if _notifier:
                    await _notifier.notify_error(result)
        except Exception:
            log.exception("Error consuming result")
            await asyncio.sleep(1)


async def _consume_state_updates() -> None:
    """Consume state updates from Rust engine (partial TP, trailing, etc.)."""
    while True:
        try:
            data = await _zmq_state_subscriber.receive()
            if data is None:
                await asyncio.sleep(0.01)
                continue
            update = StateUpdate(**data)
            log.info("State update: %s %s %s", update.update_type, update.signal_id, update.details)

            if update.update_type == "partial_tp" and _notifier:
                await _notifier.notify_partial_tp(update)
        except Exception:
            log.exception("Error consuming state update")
            await asyncio.sleep(1)


# ─── API endpoints ───────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> HealthResponse:
    uptime = time.time() - _start_time if _start_time else 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trades_today = await asyncio.get_event_loop().run_in_executor(
        None, database.get_daily_trade_count, today
    )
    return HealthResponse(
        status="ok",
        rust_engine="connected" if _zmq_producer and _zmq_producer.connected else "disconnected",
        mt5_connected=_mt5_bridge is not None and getattr(_mt5_bridge, "connected", False),
        zmq_connected=_zmq_producer is not None,
        uptime_seconds=round(uptime, 1),
        trades_today=trades_today,
        dry_run=config.DRY_RUN,
    )


@app.get("/api/trades")
async def list_trades(
    limit: int = 50,
    offset: int = 0,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, database.get_trades, limit, offset, symbol, status)


@app.get("/api/trades/open")
async def open_trades() -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, database.get_open_trades)


@app.get("/api/config")
async def get_config() -> dict:
    return {
        "bridge_mode": config.MT5_BRIDGE_MODE,
        "dry_run": config.DRY_RUN,
        "db_backend": config.DB_BACKEND,
        "zmq": {
            "signal": config.ZMQ_SIGNAL_ADDR,
            "command": config.ZMQ_COMMAND_ADDR,
            "result": config.ZMQ_RESULT_ADDR,
            "state": config.ZMQ_STATE_ADDR,
        },
        "symbols_loaded": len(_symbol_map),
    }


@app.post("/api/close-all")
async def close_all() -> JSONResponse:
    """Emergency: send closeall signal to Rust engine."""
    signal = ValidatedSignal(
        action="closeall",
        symbol="ALL",
        comment="emergency_close",
        dry_run=config.DRY_RUN,
    )
    await _zmq_producer.send(signal)
    log.warning("Emergency CLOSE ALL dispatched")
    return JSONResponse(content={"status": "close_all_dispatched", "signal_id": signal.signal_id})


@app.get("/api/analytics")
async def analytics(days: int = 30) -> dict:
    from .analytics import get_pnl_summary, get_win_rate, get_drawdown

    loop = asyncio.get_event_loop()
    pnl, winrate, dd = await asyncio.gather(
        loop.run_in_executor(None, get_pnl_summary, days),
        loop.run_in_executor(None, get_win_rate, days),
        loop.run_in_executor(None, get_drawdown, days),
    )
    return {"pnl": pnl, "win_rate": winrate, "drawdown": dd}


# ─── Dashboard ────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False, response_model=None)
def root():
    index = CLIENT_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "PineConnector API running. Dashboard not found."})


if CLIENT_DIR.exists():
    app.mount("/client", StaticFiles(directory=str(CLIENT_DIR)), name="client")
