"""FastAPI server for the PineScript Backtester.

Endpoints
---------
POST /api/backtest                Submit a new backtest
GET  /api/backtest/{id}/status    Poll backtest progress
GET  /api/backtest/{id}/report    Full MQL5-style report JSON
GET  /api/backtests               List previous backtests
DELETE /api/backtest/{id}         Delete a backtest
GET  /api/symbols/search          Symbol autocomplete
POST /api/parse                   Parse PineScript and return params
GET  /api/health                  Health check
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import quote

import io

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import database as db
from .data import (
    dataframe_to_csv_bytes,
    download_mt5_ohlcv,
    download_ohlcv,
    get_data_warning,
    save_mt5_temp_data,
    search_symbols,
)
from .models import BacktestRequest, BacktestReport, BacktestStatus, BacktestSummary, ParseResult

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="PineScript Backtester", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_DIR = Path(__file__).parent.parent / "client"


@app.on_event("startup")
def on_startup():
    db.init_db()
    log.info("Backtester database initialised")


@app.get("/", include_in_schema=False)
def root():
    index = CLIENT_DIR / "index.html"
    return FileResponse(str(index)) if index.exists() else JSONResponse(
        {"message": "Backtester API running. Frontend not found."}
    )


if CLIENT_DIR.exists():
    app.mount("/client", StaticFiles(directory=str(CLIENT_DIR)), name="client")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backtester"}


# -- Backtest submission -------------------------------------------------------

_running_tasks: dict[int, asyncio.Task] = {}


@app.post("/api/backtest")
async def submit_backtest(req: BacktestRequest):
    from datetime import datetime

    end_date = req.end_date or datetime.now().strftime("%Y-%m-%d")

    warning = get_data_warning(req.timeframe, req.start_date, end_date)

    bt_data = {
        "name": req.name or f"{req.symbol} {req.timeframe}",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "start_date": req.start_date,
        "end_date": end_date,
        "initial_capital": req.initial_capital,
        "leverage": req.leverage,
        "commission_pct": req.commission_pct,
        "slippage_points": req.slippage_points,
        "strategy_source": req.pinescript,
        "strategy_config": req.strategy_config or {},
        "input_overrides": req.input_overrides,
    }

    bt_id = db.create_backtest(bt_data)

    task = asyncio.create_task(_run_backtest(bt_id, req))
    _running_tasks[bt_id] = task

    return {
        "id": bt_id,
        "status": "pending",
        "warning": warning,
    }


async def _run_backtest(bt_id: int, req: BacktestRequest):
    from .report.generator import generate_report

    loop = asyncio.get_event_loop()
    try:
        db.update_backtest_status(bt_id, "downloading", 10, "Downloading historical data...")

        df = await loop.run_in_executor(None, lambda: download_ohlcv(
            req.symbol, req.timeframe, req.start_date,
            req.end_date or "",
        ))

        if df.empty:
            db.update_backtest_status(bt_id, "error", 0, error="No data available for this symbol/timeframe/period")
            return

        db.update_backtest_status(bt_id, "running", 30, "Parsing strategy and running backtest...")

        report = await loop.run_in_executor(None, lambda: generate_report(bt_id, req, df))

        db.update_backtest_status(bt_id, "complete", 100, "Done")

    except Exception as e:
        log.exception("Backtest %d failed", bt_id)
        db.update_backtest_status(bt_id, "error", 0, error=str(e))
    finally:
        _running_tasks.pop(bt_id, None)


@app.post("/api/backtest/mt5")
async def submit_mt5_backtest(req: BacktestRequest):
    from datetime import datetime

    end_date = req.end_date or datetime.now().strftime("%Y-%m-%d")

    bt_data = {
        "name": req.name or f"{req.symbol} {req.timeframe} (MT5)",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
        "start_date": req.start_date,
        "end_date": end_date,
        "initial_capital": req.initial_capital,
        "leverage": req.leverage,
        "commission_pct": req.commission_pct,
        "slippage_points": req.slippage_points,
        "strategy_source": req.pinescript,
        "strategy_config": req.strategy_config or {},
        "input_overrides": req.input_overrides,
    }

    bt_id = db.create_backtest(bt_data)

    task = asyncio.create_task(_run_mt5_backtest(bt_id, req))
    _running_tasks[bt_id] = task

    return {"id": bt_id, "status": "pending"}


async def _run_mt5_backtest(bt_id: int, req: BacktestRequest):
    from datetime import datetime

    from .report.generator import generate_report

    effective_end = (req.end_date or "").strip() or datetime.now().strftime("%Y-%m-%d")

    loop = asyncio.get_event_loop()
    try:
        db.update_backtest_status(bt_id, "downloading", 10, "Downloading historical data from MT5 terminal...")
        df = await loop.run_in_executor(
            None,
            lambda: download_mt5_ohlcv(req.symbol, req.timeframe, req.start_date, effective_end),
        )

        if df.empty:
            db.update_backtest_status(bt_id, "error", 0, error="No MT5 data available for this symbol/timeframe/period")
            return

        db.update_backtest_status(bt_id, "downloading", 20, "Saving temporary MT5 data locally...")
        await loop.run_in_executor(
            None,
            lambda: save_mt5_temp_data(req.symbol, req.timeframe, req.start_date, effective_end, df),
        )

        db.update_backtest_status(bt_id, "running", 35, "Parsing strategy and running backtest...")
        await loop.run_in_executor(None, lambda: generate_report(bt_id, req, df))
        db.update_backtest_status(bt_id, "complete", 100, "Done")
    except Exception as e:
        log.exception("Backtest %d failed (MT5)", bt_id)
        db.update_backtest_status(bt_id, "error", 0, error=str(e))
    finally:
        _running_tasks.pop(bt_id, None)


@app.get("/api/backtest/{bt_id}/status")
def backtest_status(bt_id: int):
    bt = db.get_backtest(bt_id)
    if not bt:
        raise HTTPException(404, "Backtest not found")
    return BacktestStatus(
        id=bt_id,
        status=bt["status"],
        progress=bt.get("progress", 0),
        phase=bt.get("phase", ""),
        error=bt.get("error"),
    )


@app.get("/api/backtest/{bt_id}/report")
def backtest_report(bt_id: int):
    bt = db.get_backtest(bt_id)
    if not bt:
        raise HTTPException(404, "Backtest not found")
    if bt["status"] != "complete":
        raise HTTPException(400, f"Backtest status: {bt['status']}")

    metrics_data = db.get_metrics(bt_id)
    equity = db.get_equity_curve(bt_id)
    orders = db.get_orders(bt_id)
    deals = db.get_deals(bt_id)
    trades = db.get_trades(bt_id)

    inputs_raw = json.loads(bt.get("strategy_config", "{}") or "{}")
    input_list = inputs_raw.get("inputs", [])

    total_commission = sum(d.get("commission", 0) for d in deals)
    total_swap = sum(d.get("swap", 0) for d in deals)
    total_profit = sum(d.get("profit", 0) for d in deals if d.get("direction") != "balance")

    return BacktestReport(
        id=bt_id,
        name=bt["name"],
        symbol=bt["symbol"],
        timeframe=bt["timeframe"],
        period=f"{bt['timeframe'].upper()} ({bt['start_date']} - {bt['end_date']})",
        initial_capital=bt["initial_capital"],
        leverage=bt["leverage"],
        commission_pct=bt["commission_pct"],
        strategy_name=bt.get("strategy_name", ""),
        inputs=input_list,
        metrics=metrics_data,
        equity_curve=[
            {"timestamp": e["timestamp"], "balance": e["balance"],
             "equity": e["equity"], "drawdown": e.get("drawdown", 0),
             "drawdown_pct": e.get("drawdown_pct", 0)}
            for e in equity
        ],
        orders=[
            {k: v for k, v in o.items() if k not in ("id", "backtest_id")}
            for o in orders
        ],
        deals=[
            {k: v for k, v in d.items() if k not in ("id", "backtest_id")}
            for d in deals
        ],
        summary={
            "total_commission": round(total_commission, 2),
            "total_swap": round(total_swap, 2),
            "total_profit": round(total_profit, 2),
            "final_balance": round(bt["initial_capital"] + total_profit + total_commission + total_swap, 2),
        },
        created_at=bt["created_at"],
    )


@app.get("/api/backtests")
def list_backtests():
    all_bt = db.get_all_backtests()
    result = []
    for bt in all_bt:
        metrics = db.get_metrics(bt["id"]) if bt["status"] == "complete" else {}
        result.append(BacktestSummary(
            id=bt["id"],
            name=bt["name"],
            symbol=bt["symbol"],
            timeframe=bt["timeframe"],
            period=f"{bt['start_date']} - {bt['end_date']}",
            strategy_name=bt.get("strategy_name", ""),
            total_net_profit=metrics.get("total_net_profit", 0),
            profit_factor=metrics.get("profit_factor", 0),
            total_trades=metrics.get("total_trades", 0),
            win_rate=metrics.get("profit_trades_pct", 0),
            max_drawdown_pct=metrics.get("equity_dd_maximal_pct", 0),
            status=bt["status"],
            created_at=bt["created_at"],
        ))
    return result


@app.delete("/api/backtest/{bt_id}")
def delete_backtest(bt_id: int):
    bt = db.get_backtest(bt_id)
    if not bt:
        raise HTTPException(404, "Backtest not found")
    db.delete_backtest(bt_id)
    return {"status": "deleted"}


@app.get("/api/mt5/download")
def download_mt5_data(
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query("1d"),
    start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(""),
):
    try:
        df = download_mt5_ohlcv(symbol, timeframe, start_date, end_date)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    if df.empty:
        raise HTTPException(404, "No MT5 data available for this symbol/timeframe/period")

    filename = f"{symbol}_{timeframe}_{start_date}_{end_date or 'latest'}_mt5.csv"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return Response(content=dataframe_to_csv_bytes(df), media_type="text/csv", headers=headers)


# -- CSV Upload backtest ------------------------------------------------------

@app.post("/api/backtest/csv")
async def submit_backtest_csv(
    file: UploadFile = File(...),
    pinescript: str = Form(""),
    symbol: str = Form("CUSTOM"),
    timeframe: str = Form("1d"),
    initial_capital: float = Form(10000),
    leverage: float = Form(1),
    commission_pct: float = Form(0),
    slippage_points: float = Form(0),
    input_overrides: str = Form("{}"),
):
    """Accept a CSV file with OHLCV data and run a backtest."""
    from datetime import datetime

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {e}")

    # Normalise column names (case-insensitive, strip whitespace)
    df.columns = [c.strip().lower() for c in df.columns]

    rename_map = {}
    for col in df.columns:
        if col in ("date", "datetime", "time", "timestamp"):
            rename_map[col] = "__date__"
        elif col in ("open", "o"):
            rename_map[col] = "open"
        elif col in ("high", "h"):
            rename_map[col] = "high"
        elif col in ("low", "l"):
            rename_map[col] = "low"
        elif col in ("close", "c"):
            rename_map[col] = "close"
        elif col in ("volume", "vol", "v", "tick_volume", "tickvol"):
            rename_map[col] = "volume"
    df.rename(columns=rename_map, inplace=True)

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"CSV missing required columns: {', '.join(missing)}. Found: {', '.join(df.columns)}")

    if "volume" not in df.columns:
        df["volume"] = 0

    if "__date__" in df.columns:
        df.index = pd.to_datetime(df["__date__"])
        df.drop(columns=["__date__"], inplace=True)
    else:
        df.index = pd.RangeIndex(len(df))

    df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)

    if df.empty:
        raise HTTPException(400, "CSV contains no valid OHLCV data after parsing")

    start_date = str(df.index[0])[:10] if hasattr(df.index[0], 'strftime') else "N/A"
    end_date = str(df.index[-1])[:10] if hasattr(df.index[-1], 'strftime') else "N/A"

    overrides = json.loads(input_overrides) if input_overrides else {}

    req = BacktestRequest(
        pinescript=pinescript,
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        leverage=leverage,
        commission_pct=commission_pct,
        slippage_points=slippage_points,
        input_overrides=overrides,
    )

    bt_data = {
        "name": f"{symbol} {timeframe} (CSV)",
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "leverage": leverage,
        "commission_pct": commission_pct,
        "slippage_points": slippage_points,
        "strategy_source": pinescript,
        "strategy_config": {},
        "input_overrides": overrides,
    }

    bt_id = db.create_backtest(bt_data)

    task = asyncio.create_task(_run_backtest_with_df(bt_id, req, df))
    _running_tasks[bt_id] = task

    return {"id": bt_id, "status": "pending", "rows": len(df)}


async def _run_backtest_with_df(bt_id: int, req: BacktestRequest, df: pd.DataFrame):
    """Run backtest using a pre-loaded DataFrame (from CSV upload)."""
    from .report.generator import generate_report

    loop = asyncio.get_event_loop()
    try:
        db.update_backtest_status(bt_id, "running", 30, "Parsing strategy and running backtest...")
        report = await loop.run_in_executor(None, lambda: generate_report(bt_id, req, df))
        db.update_backtest_status(bt_id, "complete", 100, "Done")
    except Exception as e:
        log.exception("Backtest %d failed (CSV)", bt_id)
        db.update_backtest_status(bt_id, "error", 0, error=str(e))
    finally:
        _running_tasks.pop(bt_id, None)


# -- Parse & Symbol search ----------------------------------------------------

@app.post("/api/parse")
def parse_pinescript_code(body: dict):
    from .parser import parse_pinescript

    code = body.get("code", "")
    if not code.strip():
        raise HTTPException(400, "No PineScript code provided")

    try:
        result = parse_pinescript(code)
        return result
    except Exception as e:
        log.exception("Parse error")
        return ParseResult(errors=[str(e)])


@app.get("/api/symbols/search")
async def symbol_search(q: str = Query("", min_length=1)):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: search_symbols(q))
    return results
