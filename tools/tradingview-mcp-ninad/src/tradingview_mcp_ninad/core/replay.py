"""Core replay mode logic: step through historical bars, place simulated trades."""

from __future__ import annotations

import asyncio
from typing import Any

from ..connection import evaluate, get_replay_api


def _wv(path: str) -> str:
    """Wrap a path with the TradingView watchable-value unwrap pattern."""
    return f"(function(){{ var v = {path}; return (v && typeof v === 'object' && typeof v.value === 'function') ? v.value() : v; }})()"


async def start(*, date: str | None = None) -> dict[str, Any]:
    rp = await get_replay_api()
    available = await evaluate(_wv(f"{rp}.isReplayAvailable()"))
    if not available:
        raise RuntimeError("Replay is not available for the current symbol/timeframe")
    await evaluate(f"{rp}.showReplayToolbar()")
    await asyncio.sleep(0.5)
    if date:
        await evaluate(f"{rp}.selectDate(new Date('{date}'))")
    else:
        await evaluate(f"{rp}.selectFirstAvailableDate()")
    await asyncio.sleep(1.0)

    toast = await evaluate("""
        (function() {
          var toasts = document.querySelectorAll('[class*="toast"], [class*="notification"], [class*="banner"]');
          for (var i = 0; i < toasts.length; i++) {
            var text = toasts[i].textContent || '';
            if (/data point unavailable|not available for playback/i.test(text)) return text.trim().substring(0, 200);
          }
          return null;
        })()
    """)
    if toast:
        try:
            await evaluate(f"{rp}.stopReplay()")
        except Exception:
            pass
        try:
            await evaluate(f"{rp}.hideReplayToolbar()")
        except Exception:
            pass
        raise RuntimeError(
            f'Replay date unavailable: "{toast}". Try a more recent date or switch to a higher timeframe.'
        )

    started = await evaluate(_wv(f"{rp}.isReplayStarted()"))
    current_date = await evaluate(_wv(f"{rp}.currentDate()"))
    return {"success": True, "replay_started": bool(started), "date": date or "(first available)", "current_date": current_date}


async def step() -> dict[str, Any]:
    rp = await get_replay_api()
    started = await evaluate(_wv(f"{rp}.isReplayStarted()"))
    if not started:
        raise RuntimeError("Replay is not started. Use replay_start first.")
    await evaluate(f"{rp}.doStep()")
    current_date = await evaluate(_wv(f"{rp}.currentDate()"))
    return {"success": True, "action": "step", "current_date": current_date}


async def autoplay(*, speed: int | None = None) -> dict[str, Any]:
    rp = await get_replay_api()
    started = await evaluate(_wv(f"{rp}.isReplayStarted()"))
    if not started:
        raise RuntimeError("Replay is not started. Use replay_start first.")
    if speed and speed > 0:
        await evaluate(f"{rp}.changeAutoplayDelay({speed})")
    await evaluate(f"{rp}.toggleAutoplay()")
    is_autoplay = await evaluate(_wv(f"{rp}.isAutoplayStarted()"))
    current_delay = await evaluate(_wv(f"{rp}.autoplayDelay()"))
    return {"success": True, "autoplay_active": bool(is_autoplay), "delay_ms": current_delay}


async def stop() -> dict[str, Any]:
    rp = await get_replay_api()
    started = await evaluate(_wv(f"{rp}.isReplayStarted()"))
    if not started:
        try:
            await evaluate(f"{rp}.hideReplayToolbar()")
        except Exception:
            pass
        return {"success": True, "action": "already_stopped"}
    await evaluate(f"{rp}.stopReplay()")
    try:
        await evaluate(f"{rp}.hideReplayToolbar()")
    except Exception:
        pass
    return {"success": True, "action": "replay_stopped"}


async def trade(*, action: str) -> dict[str, Any]:
    rp = await get_replay_api()
    started = await evaluate(_wv(f"{rp}.isReplayStarted()"))
    if not started:
        raise RuntimeError("Replay is not started. Use replay_start first.")
    if action == "buy":
        await evaluate(f"{rp}.buy()")
    elif action == "sell":
        await evaluate(f"{rp}.sell()")
    elif action == "close":
        await evaluate(f"{rp}.closePosition()")
    else:
        raise ValueError("Invalid action. Use: buy, sell, or close")
    position = await evaluate(_wv(f"{rp}.position()"))
    pnl = await evaluate(_wv(f"{rp}.realizedPL()"))
    return {"success": True, "action": action, "position": position, "realized_pnl": pnl}


async def status() -> dict[str, Any]:
    rp = await get_replay_api()
    st = await evaluate(
        f"""
        (function() {{
          var r = {rp};
          function unwrap(v) {{ return (v && typeof v === 'object' && typeof v.value === 'function') ? v.value() : v; }}
          return {{
            is_replay_available: unwrap(r.isReplayAvailable()),
            is_replay_started: unwrap(r.isReplayStarted()),
            is_autoplay_started: unwrap(r.isAutoplayStarted()),
            replay_mode: unwrap(r.replayMode()),
            current_date: unwrap(r.currentDate()),
            autoplay_delay: unwrap(r.autoplayDelay()),
          }};
        }})()
        """
    ) or {}
    pos = await evaluate(_wv(f"{rp}.position()"))
    pnl = await evaluate(_wv(f"{rp}.realizedPL()"))
    return {"success": True, **st, "position": pos, "realized_pnl": pnl}
