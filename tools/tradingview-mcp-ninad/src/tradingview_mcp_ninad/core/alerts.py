"""Core alert logic: create, list, and delete price alerts via DOM + REST API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import anyio

from ..connection import evaluate, evaluate_async, get_client


async def create(*, condition: str | None = None, price: float, message: str | None = None) -> dict[str, Any]:
    """Open the alert dialog, fill in the price/message, and click Create."""
    opened = await evaluate("""
        (function() {
          var btn = document.querySelector('[aria-label="Create Alert"]')
            || document.querySelector('[data-name="alerts"]');
          if (btn) { btn.click(); return true; }
          return false;
        })()
    """)

    if not opened:
        tab = await get_client()
        def _key_down():
            tab.Input.dispatchKeyEvent(type="keyDown", modifiers=1, key="a", code="KeyA", windowsVirtualKeyCode=65)
        def _key_up():
            tab.Input.dispatchKeyEvent(type="keyUp", key="a", code="KeyA")
        await anyio.to_thread.run_sync(_key_down)
        await anyio.to_thread.run_sync(_key_up)

    await asyncio.sleep(1.0)

    price_set = await evaluate(
        f"""
        (function() {{
          var inputs = document.querySelectorAll('[class*="alert"] input[type="text"], [class*="alert"] input[type="number"]');
          for (var i = 0; i < inputs.length; i++) {{
            var label = inputs[i].closest('[class*="row"]')?.querySelector('[class*="label"]');
            if (label && /value|price/i.test(label.textContent)) {{
              var nativeSet = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
              nativeSet.call(inputs[i], '{price}');
              inputs[i].dispatchEvent(new Event('input', {{ bubbles: true }}));
              inputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
              return true;
            }}
          }}
          if (inputs.length > 0) {{
            var nativeSet = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            nativeSet.call(inputs[0], '{price}');
            inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
            return true;
          }}
          return false;
        }})()
        """
    )

    if message:
        await evaluate(
            f"""
            (function() {{
              var textarea = document.querySelector('[class*="alert"] textarea')
                || document.querySelector('textarea[placeholder*="message"]');
              if (textarea) {{
                var nativeSet = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
                nativeSet.call(textarea, {json.dumps(message)});
                textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
              }}
            }})()
            """
        )

    await asyncio.sleep(0.5)
    created = await evaluate("""
        (function() {
          var btns = document.querySelectorAll('button[data-name="submit"], button');
          for (var i = 0; i < btns.length; i++) {
            if (/^create$/i.test(btns[i].textContent.trim())) { btns[i].click(); return true; }
          }
          return false;
        })()
    """)
    return {"success": bool(created), "price": price, "condition": condition, "message": message or "(none)", "price_set": bool(price_set), "source": "dom_fallback"}


async def list_alerts() -> dict[str, Any]:
    """Fetch all alerts from the pricealerts REST API (uses TradingView session cookies)."""
    result = await evaluate_async("""
        fetch('https://pricealerts.tradingview.com/list_alerts', { credentials: 'include' })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.s !== 'ok' || !Array.isArray(data.r)) return { alerts: [], error: data.errmsg || 'Unexpected response' };
            return {
              alerts: data.r.map(function(a) {
                var sym = '';
                try { sym = JSON.parse(a.symbol.replace(/^=/, '')).symbol || a.symbol; } catch(e) { sym = a.symbol; }
                return {
                  alert_id: a.alert_id, symbol: sym, type: a.type, message: a.message,
                  active: a.active, condition: a.condition, resolution: a.resolution,
                  created: a.create_time, last_fired: a.last_fire_time, expiration: a.expiration,
                };
              })
            };
          })
          .catch(function(e) { return { alerts: [], error: e.message }; })
    """) or {}
    alerts = result.get("alerts") or []
    return {"success": True, "alert_count": len(alerts), "source": "internal_api", "alerts": alerts, "error": result.get("error")}


async def delete_alerts(*, delete_all: bool = False) -> dict[str, Any]:
    if delete_all:
        result = await evaluate("""
            (function() {
              var header = document.querySelector('[data-name="alerts"]');
              if (header) {
                header.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 100, clientY: 100 }));
                return { context_menu_opened: true };
              }
              return { context_menu_opened: false };
            })()
        """) or {}
        return {"success": True, "note": "Alert deletion requires manual confirmation in the context menu.", "context_menu_opened": result.get("context_menu_opened", False), "source": "dom_fallback"}
    raise RuntimeError("Individual alert deletion not yet supported. Use delete_all: true.")
