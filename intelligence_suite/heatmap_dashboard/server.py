"""
Intelligence Suite — Heatmap Dashboard Server
================================================
FastAPI application serving portfolio heatmap, VaR, and stress-test data.
"""

import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from intelligence_suite.heatmap_dashboard.portfolio_analyzer import PortfolioAnalyzer
from intelligence_suite.heatmap_dashboard.stress_tester import StressTester
from intelligence_suite.heatmap_dashboard.var_calculator import VaRCalculator

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
heatmap_cfg = config.get("heatmap", {})
PORT = int(os.environ.get("HEATMAP_PORT", heatmap_cfg.get("port", 8061)))

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
analyzer = PortfolioAnalyzer(config)
var_calc = VaRCalculator()
stress = StressTester()

# Optional MT5 connector
mt5_connector = None


def _get_mt5():
    """Lazy-load MT5 connector."""
    global mt5_connector
    if mt5_connector is not None:
        return mt5_connector
    try:
        from intelligence_suite.shared.mt5_connector import MT5Connector
        mt5_connector = MT5Connector(config)
        return mt5_connector
    except Exception as exc:
        logger.warning(f"MT5 not available, using demo data: {exc}")
        return None


def _demo_positions() -> list[dict]:
    """Return demo positions when MT5 is unavailable."""
    return [
        {"symbol": "BTCUSD", "type": "BUY", "volume": 0.5, "price_open": 42000,
         "price_current": 43200, "profit": 600, "sl": 41000, "tp": 45000},
        {"symbol": "ETHUSD", "type": "BUY", "volume": 2.0, "price_open": 2800,
         "price_current": 2950, "profit": 300, "sl": 2700, "tp": 3100},
        {"symbol": "XAUUSD", "type": "SELL", "volume": 0.1, "price_open": 2050,
         "price_current": 2030, "profit": 200, "sl": 2100, "tp": 1980},
        {"symbol": "EURUSD", "type": "BUY", "volume": 1.0, "price_open": 1.0850,
         "price_current": 1.0890, "profit": 40, "sl": 1.0800, "tp": 1.0950},
        {"symbol": "SOLUSD", "type": "BUY", "volume": 10.0, "price_open": 98,
         "price_current": 105, "profit": 70, "sl": 90, "tp": 120},
    ]


def _get_positions() -> list[dict]:
    """Get positions from MT5 or demo data."""
    conn = _get_mt5()
    if conn and conn.connected:
        positions = conn.get_positions()
        if positions:
            return positions
    return _demo_positions()


def _get_account_info() -> dict:
    """Get account info from MT5 or demo data."""
    conn = _get_mt5()
    if conn and conn.connected:
        info = conn.get_account_info()
        if info:
            return info
    return {
        "balance": 100000, "equity": 101210, "profit": 1210,
        "margin": 5200, "free_margin": 96010, "leverage": 100,
        "currency": "USD", "login": 0, "server": "demo",
    }


def _generate_returns(n_days: int = 252) -> pd.Series:
    """Generate synthetic returns for VaR when no real data is available."""
    rng = np.random.default_rng(seed=123)
    return pd.Series(rng.normal(0.0005, 0.02, n_days))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Portfolio Heat Map Dashboard",
    version="1.0.0",
    docs_url="/docs",
)


@app.get("/api/portfolio")
async def get_portfolio():
    """Return current portfolio analysis."""
    try:
        positions = _get_positions()
        analysis = analyzer.analyze(positions)
        account = _get_account_info()
        return JSONResponse(content={
            "account": account,
            "analysis": analysis,
            "positions": positions,
        })
    except Exception as exc:
        logger.error(f"Portfolio analysis failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/var")
async def get_var():
    """Return VaR calculations (all three methods)."""
    try:
        account = _get_account_info()
        equity = account.get("equity", 100000)
        returns = _generate_returns()
        confidence = heatmap_cfg.get("var_confidence", 0.95)
        n_sims = heatmap_cfg.get("monte_carlo_simulations", 10000)

        historical = var_calc.historical_var(returns, confidence, equity)
        parametric = var_calc.parametric_var(returns, confidence, equity)
        monte_carlo = var_calc.monte_carlo_var(
            returns, confidence, equity, n_simulations=n_sims
        )

        return JSONResponse(content={
            "portfolio_value": equity,
            "confidence": confidence,
            "historical": historical,
            "parametric": parametric,
            "monte_carlo": monte_carlo,
        })
    except Exception as exc:
        logger.error(f"VaR calculation failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/stress")
async def get_stress():
    """Return stress-test results for all scenarios."""
    try:
        positions = _get_positions()
        account = _get_account_info()
        equity = account.get("equity", 100000)
        results = stress.run_stress_test(equity, positions)
        return JSONResponse(content=results)
    except Exception as exc:
        logger.error(f"Stress test failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/heatmap")
async def get_heatmap():
    """Return treemap data suitable for D3.js visualization."""
    try:
        positions = _get_positions()
        analysis = analyzer.analyze(positions)

        # Build D3-compatible treemap structure
        children: list[dict] = []
        for asset_type, data in analysis.get("per_asset_type_exposure", {}).items():
            asset_children: list[dict] = []
            for pos in positions:
                from intelligence_suite.heatmap_dashboard.portfolio_analyzer import ASSET_TYPE_MAP
                if ASSET_TYPE_MAP.get(pos.get("symbol", ""), "unknown") == asset_type:
                    profit = float(pos.get("profit", 0))
                    notional = float(pos.get("volume", 0)) * float(
                        pos.get("price_current", pos.get("current_price", 0))
                    )
                    asset_children.append({
                        "name": pos.get("symbol", ""),
                        "value": round(abs(notional), 2),
                        "profit": round(profit, 2),
                        "direction": pos.get("type", "BUY"),
                        "volume": pos.get("volume", 0),
                    })
            if asset_children:
                children.append({
                    "name": asset_type,
                    "children": asset_children,
                })

        treemap = {"name": "portfolio", "children": children}
        return JSONResponse(content={"treemap": treemap, "analysis": analysis})
    except Exception as exc:
        logger.error(f"Heatmap generation failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "heatmap_dashboard"}


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
    """Entry point for running the dashboard server."""
    from intelligence_suite.shared.logging_config import setup_logging
    setup_logging(config.get("logging", {}).get("level", "INFO"))
    logger.info(f"Starting Heatmap Dashboard on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
