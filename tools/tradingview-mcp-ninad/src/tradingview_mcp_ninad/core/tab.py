"""Core tab management: list, create, close, and switch between chart tabs."""

from __future__ import annotations

import asyncio
import os
import platform
import re
from typing import Any

import anyio
import httpx

from ..connection import get_client

CDP_HOST: str = os.environ.get("TVMCP_CDP_HOST", "localhost")
CDP_PORT: int = int(os.environ.get("TVMCP_CDP_PORT", "9222"))


async def list_tabs() -> dict[str, Any]:
    """Enumerate open TradingView chart tabs via the CDP /json/list endpoint."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        resp = await client.get(f"http://{CDP_HOST}:{CDP_PORT}/json/list")
        resp.raise_for_status()
        targets = resp.json()
    tabs = []
    for i, t in enumerate(targets):
        if t.get("type") != "page":
            continue
        if not re.search(r"tradingview\.com/chart", t.get("url", ""), re.IGNORECASE):
            continue
        chart_id_match = re.search(r"/chart/([^/?]+)", t.get("url", ""))
        tabs.append({
            "index": len(tabs),
            "id": t["id"],
            "title": re.sub(r"^Live stock.*charts on ", "", t.get("title", "")),
            "url": t["url"],
            "chart_id": chart_id_match.group(1) if chart_id_match else None,
        })
    return {"success": True, "tab_count": len(tabs), "tabs": tabs}


async def new_tab() -> dict[str, Any]:
    """Open a new chart tab via keyboard shortcut (Ctrl+T / Cmd+T)."""
    tab = await get_client()
    is_mac = platform.system().lower() == "darwin"
    mod = 4 if is_mac else 2  # 4 = meta (Cmd), 2 = ctrl

    def _key_cmd():
        tab.Input.dispatchKeyEvent(type="keyDown", modifiers=mod, key="t", code="KeyT", windowsVirtualKeyCode=84)
        tab.Input.dispatchKeyEvent(type="keyUp", key="t", code="KeyT")

    await anyio.to_thread.run_sync(_key_cmd)
    await asyncio.sleep(2.0)
    state = await list_tabs()
    return {"success": True, "action": "new_tab_opened", **state}


async def close_tab() -> dict[str, Any]:
    """Close the current tab via keyboard shortcut (Ctrl+W / Cmd+W)."""
    before = await list_tabs()
    if before["tab_count"] <= 1:
        raise RuntimeError("Cannot close the last tab. Use tv_launch to restart TradingView instead.")
    tab = await get_client()
    is_mac = platform.system().lower() == "darwin"
    mod = 4 if is_mac else 2

    def _key_cmd():
        tab.Input.dispatchKeyEvent(type="keyDown", modifiers=mod, key="w", code="KeyW", windowsVirtualKeyCode=87)
        tab.Input.dispatchKeyEvent(type="keyUp", key="w", code="KeyW")

    await anyio.to_thread.run_sync(_key_cmd)
    await asyncio.sleep(1.0)
    after = await list_tabs()
    return {"success": True, "action": "tab_closed", "tabs_before": before["tab_count"], "tabs_after": after["tab_count"]}


async def switch_tab(*, index: int) -> dict[str, Any]:
    """Switch to a tab by index using the CDP activate endpoint."""
    tabs = await list_tabs()
    if index >= tabs["tab_count"]:
        raise RuntimeError(f"Tab index {index} out of range (have {tabs['tab_count']} tabs)")
    target = tabs["tabs"][index]
    async with httpx.AsyncClient(timeout=2.0) as client:
        resp = await client.get(f"http://{CDP_HOST}:{CDP_PORT}/json/activate/{target['id']}")
        resp.raise_for_status()
    return {"success": True, "action": "switched", "index": index, "tab_id": target["id"], "chart_id": target.get("chart_id")}
