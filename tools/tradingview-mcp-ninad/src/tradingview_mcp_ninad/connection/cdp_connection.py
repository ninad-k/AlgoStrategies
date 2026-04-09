"""Singleton Chrome DevTools Protocol connection to TradingView Desktop.

The connection lifecycle mirrors the original Node project so behavior is
identical from the model's perspective:

* A single ``pychrome.Tab`` instance is reused across tool calls.
* Each reuse runs a cheap ``Runtime.evaluate("1")`` liveness probe — TV
  occasionally tears down its main page on layout changes, and a stale tab
  reference would deadlock the next real call.
* On failure we drop the cached tab and reconnect with exponential backoff
  capped at 30 seconds, matching the JS retry policy.

``pychrome`` is synchronous, so all blocking calls are bounced through
``anyio.to_thread.run_sync`` to keep the FastMCP event loop responsive.
"""

from __future__ import annotations

import os
from typing import Any

import anyio
import httpx
import pychrome
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger(__name__)

# Defaults match the original; ``TVMCP_CDP_HOST`` / ``TVMCP_CDP_PORT`` allow
# overrides without editing source — useful when running TradingView in a
# remote profile or container.
CDP_HOST: str = os.environ.get("TVMCP_CDP_HOST", "localhost")
CDP_PORT: int = int(os.environ.get("TVMCP_CDP_PORT", "9222"))
MAX_RETRIES: int = 5
BASE_DELAY_SECONDS: float = 0.5
MAX_DELAY_SECONDS: float = 30.0

# Module-level state. Guarded by the GIL for the simple read-or-replace
# pattern used here; finer locking is unnecessary because all callers go
# through ``get_client`` which serializes the reconnect path itself.
_browser: pychrome.Browser | None = None
_tab: pychrome.Tab | None = None
_target_info: dict[str, Any] | None = None


class CdpConnectionError(RuntimeError):
    """Raised when no usable TradingView CDP target can be reached."""


async def get_client() -> pychrome.Tab:
    """Return a live tab, reconnecting on the first sign of trouble.

    The liveness probe is the only safe way to detect a tab that the
    TradingView app has discarded — the underlying socket stays open long
    after the page is gone.
    """
    global _tab
    if _tab is not None:
        try:
            await _evaluate_raw(_tab, "1")
            return _tab
        except Exception:  # noqa: BLE001 — any failure means we must reconnect
            log.info("cdp.liveness_failed", action="reconnect")
            _reset_state()
    return await connect()


async def connect() -> pychrome.Tab:
    """Discover a TradingView page target and attach a fresh CDP tab to it."""
    global _browser, _tab, _target_info
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(
            multiplier=BASE_DELAY_SECONDS,
            max=MAX_DELAY_SECONDS,
        ),
        retry=retry_if_exception_type(CdpConnectionError),
        reraise=True,
    ):
        with attempt:
            target = await _find_chart_target()
            if target is None:
                raise CdpConnectionError(
                    "No TradingView chart target found. Is TradingView open with a chart?"
                )
            browser = pychrome.Browser(url=f"http://{CDP_HOST}:{CDP_PORT}")
            tab = await anyio.to_thread.run_sync(browser.list_tab)  # type: ignore[arg-type]
            # ``list_tab`` returns every tab; pick the one whose id matches.
            tab = next((t for t in tab if t.id == target["id"]), None)
            if tab is None:
                raise CdpConnectionError(
                    f"CDP target {target['id']!r} disappeared between discovery and attach"
                )
            await anyio.to_thread.run_sync(tab.start)
            await anyio.to_thread.run_sync(tab.Runtime.enable)
            await anyio.to_thread.run_sync(tab.Page.enable)
            await anyio.to_thread.run_sync(tab.DOM.enable)
            _browser = browser
            _tab = tab
            _target_info = target
            log.info("cdp.connected", target_url=target.get("url"))
            return tab
    raise CdpConnectionError("unreachable")  # pragma: no cover


async def _find_chart_target() -> dict[str, Any] | None:
    """Locate a chart-bearing TradingView page among the debugger's tabs.

    Prefers ``tradingview.com/chart`` URLs (the actual chart frame); falls
    back to any TradingView page so the connection still attaches when the
    user is on the symbol overview or watchlist screen.
    """
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/list"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            targets: list[dict[str, Any]] = resp.json()
    except httpx.HTTPError as exc:
        raise CdpConnectionError(
            f"Cannot reach Chrome DevTools at {url}: {exc}"
        ) from exc

    pages = [t for t in targets if t.get("type") == "page"]
    chart_url = next(
        (t for t in pages if "tradingview.com/chart" in (t.get("url") or "").lower()),
        None,
    )
    if chart_url is not None:
        return chart_url
    return next(
        (t for t in pages if "tradingview" in (t.get("url") or "").lower()),
        None,
    )


async def get_target_info() -> dict[str, Any] | None:
    """Return metadata about the currently attached page (lazy connect)."""
    if _target_info is None:
        await get_client()
    return _target_info


async def evaluate(expression: str, *, await_promise: bool = False) -> Any:
    """Run a JS expression in the page and return its serialized value.

    ``await_promise`` is wired through so a single helper covers both sync
    expressions and ``async``-style ones (used heavily by Pine tooling).
    """
    tab = await get_client()
    return await _evaluate_raw(tab, expression, await_promise=await_promise)


async def evaluate_async(expression: str) -> Any:
    """Convenience wrapper for promise-returning JS expressions."""
    return await evaluate(expression, await_promise=True)


async def _evaluate_raw(
    tab: pychrome.Tab,
    expression: str,
    *,
    await_promise: bool = False,
) -> Any:
    """Low-level eval helper used by both the public API and the liveness probe.

    Surfaces JS exceptions as Python ``RuntimeError`` so tools higher up can
    catch a single exception type instead of poking at CDP response shape.
    """

    def _call() -> dict[str, Any]:
        return tab.Runtime.evaluate(
            expression=expression,
            returnByValue=True,
            awaitPromise=await_promise,
        )

    result = await anyio.to_thread.run_sync(_call)
    if "exceptionDetails" in result and result["exceptionDetails"]:
        details = result["exceptionDetails"]
        message = (
            (details.get("exception") or {}).get("description")
            or details.get("text")
            or "Unknown evaluation error"
        )
        raise RuntimeError(f"JS evaluation error: {message}")
    return (result.get("result") or {}).get("value")


async def disconnect() -> None:
    """Close the active CDP tab and clear cached state.

    Best-effort: any error during shutdown is logged and swallowed because
    the only caller is process teardown.
    """
    global _browser, _tab, _target_info
    if _tab is not None:
        try:
            await anyio.to_thread.run_sync(_tab.stop)
        except Exception as exc:  # noqa: BLE001
            log.info("cdp.disconnect_error", error=str(exc))
    _reset_state()


def _reset_state() -> None:
    """Drop cached browser/tab references so the next call reconnects fresh."""
    global _browser, _tab, _target_info
    _browser = None
    _tab = None
    _target_info = None
