"""Core watchlist logic: read and add symbols using DOM introspection + input dispatch."""

from __future__ import annotations

import asyncio
from typing import Any

import anyio

from ..connection import evaluate, get_client


async def get_watchlist() -> dict[str, Any]:
    """Read symbol rows from the right-panel watchlist widget."""
    symbols = await evaluate("""
        (function() {
          try {
            var rightArea = document.querySelector('[class*="layout__area--right"]');
            if (!rightArea || rightArea.offsetWidth < 50) return { symbols: [], source: 'panel_closed' };
          } catch(e) {}
          var results = [];
          var seen = {};
          var container = document.querySelector('[class*="layout__area--right"]');
          if (!container) return { symbols: [], source: 'no_container' };
          var symbolEls = container.querySelectorAll('[data-symbol-full]');
          for (var i = 0; i < symbolEls.length; i++) {
            var sym = symbolEls[i].getAttribute('data-symbol-full');
            if (!sym || seen[sym]) continue;
            seen[sym] = true;
            var row = symbolEls[i].closest('[class*="row"]') || symbolEls[i].parentElement;
            var cells = row ? row.querySelectorAll('[class*="cell"], [class*="column"]') : [];
            var nums = [];
            for (var j = 0; j < cells.length; j++) {
              var t = cells[j].textContent.trim();
              if (t && /^[\\-+]?[\\d,]+\\.?\\d*%?$/.test(t.replace(/[\\s,]/g, ''))) nums.push(t);
            }
            results.push({ symbol: sym, last: nums[0] || null, change: nums[1] || null, change_percent: nums[2] || null });
          }
          if (results.length > 0) return { symbols: results, source: 'data_attributes' };
          var items = container.querySelectorAll('[class*="symbolName"], [class*="tickerName"], [class*="symbol-"]');
          for (var k = 0; k < items.length; k++) {
            var text = items[k].textContent.trim();
            if (text && /^[A-Z][A-Z0-9.:!]{0,20}$/.test(text) && !seen[text]) {
              seen[text] = true;
              results.push({ symbol: text, last: null, change: null, change_percent: null });
            }
          }
          return { symbols: results, source: results.length > 0 ? 'text_scan' : 'empty' };
        })()
    """) or {}
    return {
        "success": True,
        "count": len(symbols.get("symbols") or []),
        "source": symbols.get("source", "unknown"),
        "symbols": symbols.get("symbols", []),
    }


async def add_symbol(*, symbol: str) -> dict[str, Any]:
    """Click the '+' button in the watchlist, type the symbol, and press Enter."""
    tab = await get_client()

    # Ensure the panel is open
    panel_state = await evaluate("""
        (function() {
          var btn = document.querySelector('[data-name="base-watchlist-widget-button"]')
            || document.querySelector('[aria-label*="Watchlist"]');
          if (!btn) return { error: 'Watchlist button not found' };
          var isActive = btn.getAttribute('aria-pressed') === 'true'
            || btn.classList.toString().indexOf('Active') !== -1;
          if (!isActive) { btn.click(); return { opened: true }; }
          return { opened: false };
        })()
    """)
    if panel_state and panel_state.get("error"):
        raise RuntimeError(panel_state["error"])
    if panel_state and panel_state.get("opened"):
        await asyncio.sleep(0.5)

    add_clicked = await evaluate("""
        (function() {
          var selectors = ['[data-name="add-symbol-button"]', '[aria-label="Add symbol"]', '[aria-label*="Add symbol"]', 'button[class*="addSymbol"]'];
          for (var s = 0; s < selectors.length; s++) {
            var btn = document.querySelector(selectors[s]);
            if (btn && btn.offsetParent !== null) { btn.click(); return { found: true }; }
          }
          var container = document.querySelector('[class*="layout__area--right"]');
          if (container) {
            var buttons = container.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
              var ariaLabel = buttons[i].getAttribute('aria-label') || '';
              if (/add.*symbol/i.test(ariaLabel) || buttons[i].textContent.trim() === '+') { buttons[i].click(); return { found: true }; }
            }
          }
          return { found: false };
        })()
    """)
    if not (add_clicked and add_clicked.get("found")):
        raise RuntimeError("Add symbol button not found in watchlist panel")
    await asyncio.sleep(0.3)

    def _type_symbol():
        tab.Input.insertText(text=symbol)
    await anyio.to_thread.run_sync(_type_symbol)
    await asyncio.sleep(0.5)

    def _press_enter():
        tab.Input.dispatchKeyEvent(type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
        tab.Input.dispatchKeyEvent(type="keyUp", key="Enter", code="Enter")
    await anyio.to_thread.run_sync(_press_enter)
    await asyncio.sleep(0.5)

    # Dismiss the search with Escape
    def _press_escape():
        tab.Input.dispatchKeyEvent(type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        tab.Input.dispatchKeyEvent(type="keyUp", key="Escape", code="Escape")
    await anyio.to_thread.run_sync(_press_escape)

    return {"success": True, "symbol": symbol, "action": "added"}
