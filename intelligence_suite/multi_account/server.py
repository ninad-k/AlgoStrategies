"""
Intelligence Suite — Multi-Account Aggregator Server
=======================================================
FastAPI application for managing multiple MT5 accounts with
consolidated positions, P&L, and risk allocation.
"""

import logging
import os
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from intelligence_suite.multi_account.account_manager import AccountManager
from intelligence_suite.multi_account.consolidated_pnl import ConsolidatedPnL
from intelligence_suite.multi_account.risk_allocator import RiskAllocator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


config = _load_config()
multi_cfg = config.get("multi_account", {})
PORT = int(os.environ.get("MULTI_ACCOUNT_PORT", multi_cfg.get("port", 8062)))

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
accounts_cfg = multi_cfg.get("accounts", [])
if not accounts_cfg:
    # Use demo accounts when no real accounts are configured
    accounts_cfg = [
        {"login": 10001, "password": "", "server": "Demo", "label": "Main"},
        {"login": 10002, "password": "", "server": "Demo", "label": "Hedge"},
    ]

account_mgr = AccountManager(accounts_cfg)
pnl_calc = ConsolidatedPnL()
risk_alloc = RiskAllocator()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Multi-Account Aggregator",
    version="1.0.0",
    docs_url="/docs",
)


@app.get("/api/accounts")
async def get_accounts():
    """Return status of all configured accounts."""
    try:
        status = account_mgr.get_account_status()
        balances = account_mgr.get_all_balances()
        return JSONResponse(content={
            "accounts": status,
            "balances": balances,
        })
    except Exception as exc:
        logger.error(f"Accounts endpoint failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/positions")
async def get_positions():
    """Return all positions across all accounts."""
    try:
        positions = account_mgr.get_all_positions()
        return JSONResponse(content={
            "position_count": len(positions),
            "positions": positions,
        })
    except Exception as exc:
        logger.error(f"Positions endpoint failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/pnl")
async def get_pnl():
    """Return consolidated P&L across all accounts."""
    try:
        positions = account_mgr.get_all_positions()
        result = pnl_calc.calculate(positions)
        return JSONResponse(content=result)
    except Exception as exc:
        logger.error(f"PnL endpoint failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/allocations")
async def get_allocations():
    """Return risk allocations for all accounts."""
    try:
        balances = account_mgr.get_all_balances()
        risk_pct = config.get("risk_management", {}).get("max_daily_loss_pct", 2.0)
        result = risk_alloc.allocate(balances, total_risk_pct=risk_pct)
        return JSONResponse(content=result)
    except Exception as exc:
        logger.error(f"Allocations endpoint failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "multi_account_aggregator"}


@app.get("/")
async def index():
    """Serve the main dashboard page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(
        content={"error": "Dashboard UI not found", "api_docs": "/docs"},
        status_code=404,
    )


# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main():
    """Entry point for running the multi-account server."""
    from intelligence_suite.shared.logging_config import setup_logging
    setup_logging(config.get("logging", {}).get("level", "INFO"))
    logger.info(f"Starting Multi-Account Aggregator on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
