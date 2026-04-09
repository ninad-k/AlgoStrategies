"""Core UI interaction logic: click, type, keyboard, panels, layouts, scroll, find, eval.

These helpers drive TradingView's DOM through CDP Input events and JS
evaluation. They're the escape hatch for actions that don't have a dedicated
TradingView API — anything a human would do via mouse or keyboard.
"""

from __future__ import annotations

import json
import platform
from typing import Any

import anyio

from ..connection import evaluate, evaluate_async, get_client


async def click(*, selector: str) -> dict[str, Any]:
    """Click a UI element by aria-label, data-name, text content, or CSS class."""
    result = await evaluate(
        f"""
        (function() {{
          var query = {json.dumps(selector)};
          var el = document.querySelector('[aria-label="' + query + '"]')
            || document.querySelector('[data-name="' + query + '"]')
            || document.querySelector(query);
          if (!el) {{
            var all = document.querySelectorAll('button, [role="button"], a, [tabindex]');
            for (var i = 0; i < all.length; i++) {{
              if (all[i].textContent.trim() === query || (all[i].getAttribute('aria-label') || '').includes(query)) {{ el = all[i]; break; }}
            }}
          }}
          if (!el) return {{ found: false, error: 'Element not found: ' + query }};
          el.click();
          return {{ found: true, tag: el.tagName, text: el.textContent.trim().substring(0, 40) }};
        }})()
        """
    )
    if result and not result.get("found"):
        raise RuntimeError(result.get("error", "Element not found"))
    return {"success": True, **(result or {})}


async def keyboard(*, key: str, modifiers: str | None = None) -> dict[str, Any]:
    """Dispatch a keyboard event, optionally with modifier keys."""
    tab = await get_client()
    platform.system().lower() == "darwin"
    mod_val = 0
    if modifiers:
        for m in modifiers.lower().split("+"):
            m = m.strip()
            if m in ("ctrl", "control"):
                mod_val |= 2
            elif m in ("alt", "option"):
                mod_val |= 1
            elif m in ("shift",):
                mod_val |= 8
            elif m in ("meta", "cmd", "command"):
                mod_val |= 4

    def _dispatch():
        tab.Input.dispatchKeyEvent(type="keyDown", modifiers=mod_val, key=key, code=f"Key{key.upper()}" if len(key) == 1 else key)
        tab.Input.dispatchKeyEvent(type="keyUp", key=key)

    await anyio.to_thread.run_sync(_dispatch)
    return {"success": True, "key": key, "modifiers": modifiers}


async def type_text(*, text: str) -> dict[str, Any]:
    """Type text into the currently focused input."""
    tab = await get_client()
    def _type():
        tab.Input.insertText(text=text)
    await anyio.to_thread.run_sync(_type)
    return {"success": True, "typed": text}


async def hover(*, selector: str) -> dict[str, Any]:
    """Move the cursor over an element to trigger hover states."""
    result = await evaluate(
        f"""
        (function() {{
          var query = {json.dumps(selector)};
          var el = document.querySelector('[aria-label="' + query + '"]')
            || document.querySelector('[data-name="' + query + '"]')
            || document.querySelector(query);
          if (!el) return {{ found: false }};
          var rect = el.getBoundingClientRect();
          return {{ found: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }};
        }})()
        """
    )
    if not result or not result.get("found"):
        raise RuntimeError(f"Element not found for hover: {selector}")
    tab = await get_client()
    def _move():
        tab.Input.dispatchMouseEvent(type="mouseMoved", x=int(result["x"]), y=int(result["y"]))
    await anyio.to_thread.run_sync(_move)
    return {"success": True, "selector": selector}


async def mouse_click(*, x: int, y: int, button: str = "left") -> dict[str, Any]:
    """Click at exact pixel coordinates."""
    tab = await get_client()
    btn = button.lower()
    cdp_btn = "left" if btn == "left" else ("right" if btn == "right" else "middle")
    def _click():
        tab.Input.dispatchMouseEvent(type="mousePressed", x=x, y=y, button=cdp_btn, clickCount=1)
        tab.Input.dispatchMouseEvent(type="mouseReleased", x=x, y=y, button=cdp_btn, clickCount=1)
    await anyio.to_thread.run_sync(_click)
    return {"success": True, "x": x, "y": y, "button": btn}


async def open_panel(*, panel: str) -> dict[str, Any]:
    """Toggle a TradingView panel by name (pine-editor, strategy-tester, watchlist, alerts, trading)."""
    result = await evaluate(
        f"""
        (function() {{
          var panel = {json.dumps(panel)};
          var map = {{
            'pine-editor': ['[data-name="open-pine-editor"]', '[aria-label*="Pine"]'],
            'pine': ['[data-name="open-pine-editor"]', '[aria-label*="Pine"]'],
            'strategy-tester': ['[data-name="backtesting"]', '[aria-label*="Strategy"]'],
            'strategy': ['[data-name="backtesting"]', '[aria-label*="Strategy"]'],
            'watchlist': ['[data-name="base-watchlist-widget-button"]', '[aria-label*="Watchlist"]'],
            'alerts': ['[data-name="alerts"]', '[aria-label*="Alerts"]'],
            'trading': ['[data-name="trading-panel"]', '[aria-label*="Trading"]'],
          }};
          var selectors = map[panel.toLowerCase()] || [panel];
          for (var s = 0; s < selectors.length; s++) {{
            var el = document.querySelector(selectors[s]);
            if (el) {{ el.click(); return {{ opened: true, selector: selectors[s] }}; }}
          }}
          return {{ opened: false, error: 'Panel button not found: ' + panel }};
        }})()
        """
    )
    if result and not result.get("opened"):
        raise RuntimeError(result.get("error", "Panel not found"))
    return {"success": True, "panel": panel, **(result or {})}


async def fullscreen() -> dict[str, Any]:
    """Toggle fullscreen mode."""
    await evaluate("document.querySelector('[data-name=\"fullscreen\"]')?.click()")
    return {"success": True, "action": "fullscreen_toggled"}


async def layout_list() -> dict[str, Any]:
    """List saved chart layouts."""
    result = await evaluate_async("""
        (function() {
          try {
            var fn = window.TradingViewApi.getSavedCharts;
            if (fn) {
              var layouts = fn();
              if (layouts && typeof layouts.then === 'function') return layouts;
              return layouts;
            }
            return [];
          } catch(e) { return { error: e.message }; }
        })()
    """) or []
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, "count": len(result) if isinstance(result, list) else 0, "layouts": result}


async def layout_switch(*, name: str) -> dict[str, Any]:
    """Load a saved chart layout by name or ID."""
    result = await evaluate(
        f"""
        (function() {{
          var name = {json.dumps(name)};
          try {{
            var fn = window.TradingViewApi.loadChart;
            if (fn) {{ fn(name); return {{ loaded: true }}; }}
            return {{ loaded: false, error: 'loadChart function not available' }};
          }} catch(e) {{ return {{ loaded: false, error: e.message }}; }}
        }})()
        """
    )
    return {"success": True, "name": name, **(result or {})}


async def scroll(*, direction: str, amount: int = 3) -> dict[str, Any]:
    """Scroll the chart viewport."""
    tab = await get_client()
    dx = amount * 100 * (-1 if direction == "left" else 1 if direction == "right" else 0)
    dy = amount * 100 * (-1 if direction == "up" else 1 if direction == "down" else 0)
    def _scroll():
        tab.Input.dispatchMouseEvent(type="mouseWheel", x=400, y=400, deltaX=dx, deltaY=dy)
    await anyio.to_thread.run_sync(_scroll)
    return {"success": True, "direction": direction, "amount": amount}


async def find_element(*, query: str) -> dict[str, Any]:
    """Search for elements by text, aria-label, or CSS selector."""
    result = await evaluate(
        f"""
        (function() {{
          var q = {json.dumps(query)};
          var matches = [];
          var all = document.querySelectorAll('*');
          for (var i = 0; i < all.length && matches.length < 10; i++) {{
            var el = all[i];
            if (el.offsetParent === null || el.offsetWidth < 5) continue;
            var text = el.textContent.trim().substring(0, 60);
            var aria = el.getAttribute('aria-label') || '';
            var dn = el.getAttribute('data-name') || '';
            if (text.includes(q) || aria.includes(q) || dn.includes(q)) {{
              var rect = el.getBoundingClientRect();
              matches.push({{ tag: el.tagName, text: text.substring(0, 40), aria: aria.substring(0, 40), data_name: dn, x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) }});
            }}
          }}
          return matches;
        }})()
        """
    ) or []
    return {"success": True, "count": len(result), "matches": result}


async def js_evaluate(*, expression: str) -> dict[str, Any]:
    """Execute arbitrary JavaScript in the page context (escape hatch)."""
    result = await evaluate(expression)
    return {"success": True, "result": result}
