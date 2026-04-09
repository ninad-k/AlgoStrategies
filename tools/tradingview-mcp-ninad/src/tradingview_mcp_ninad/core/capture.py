"""Core screenshot/capture logic via CDP Page.captureScreenshot."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

import anyio

from ..connection import evaluate, get_chart_collection, get_client
from ..logging_config import state_dir

SCREENSHOT_DIR = state_dir() / "screenshots"


async def capture_screenshot(
    *,
    region: str | None = None,
    filename: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Take a PNG screenshot of the chart or a specific panel."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    fname = filename or f"tv_{region or 'full'}_{ts}"
    file_path = SCREENSHOT_DIR / f"{fname}.png"

    if method == "api":
        try:
            col_path = await get_chart_collection()
            await evaluate(f"{col_path}.takeScreenshot()")
            return {
                "success": True,
                "method": "api",
                "note": "takeScreenshot() triggered — TradingView will save/show the screenshot via its own UI",
            }
        except Exception:
            pass  # fall through to CDP

    tab = await get_client()
    clip = None

    if region == "chart":
        bounds = await evaluate("""
            (function() {
              var el = document.querySelector('[data-name="pane-canvas"]')
                || document.querySelector('[class*="chart-container"]')
                || document.querySelector('canvas');
              if (!el) return null;
              var rect = el.getBoundingClientRect();
              return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
            })()
        """)
        if bounds:
            clip = {k: bounds[k] for k in ("x", "y", "width", "height")}
            clip["scale"] = 1
    elif region == "strategy_tester":
        bounds = await evaluate("""
            (function() {
              var el = document.querySelector('[data-name="backtesting"]')
                || document.querySelector('[class*="strategyReport"]');
              if (!el) return null;
              var rect = el.getBoundingClientRect();
              return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
            })()
        """)
        if bounds:
            clip = {k: bounds[k] for k in ("x", "y", "width", "height")}
            clip["scale"] = 1

    params: dict[str, Any] = {"format": "png"}
    if clip:
        params["clip"] = clip

    def _screenshot():
        return tab.Page.captureScreenshot(**params)

    result = await anyio.to_thread.run_sync(_screenshot)
    data_b64 = result.get("data", "")
    raw = base64.b64decode(data_b64)
    file_path.write_bytes(raw)

    return {
        "success": True,
        "method": "cdp",
        "file_path": str(file_path),
        "region": region,
        "size_bytes": len(raw),
    }
