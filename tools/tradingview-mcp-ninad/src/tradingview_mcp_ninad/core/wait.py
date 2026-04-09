"""Chart readiness polling helper.

After changing symbol or resolution, TradingView reloads data asynchronously.
The wait helper polls the DOM for loading spinners and bar-count stability so
that the next tool call sees a fully rendered chart instead of a half-loaded
skeleton. The strategy — three consecutive equal bar counts with no loading
spinner visible — mirrors the original JS implementation.
"""

from __future__ import annotations

import asyncio
import time

from ..connection import evaluate

DEFAULT_TIMEOUT_SECONDS: float = 10.0
POLL_INTERVAL_SECONDS: float = 0.2


async def wait_for_chart_ready(
    expected_symbol: str | None = None,
    expected_timeframe: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> bool:
    """Block until the chart appears settled, then return ``True``.

    Returns ``False`` if the timeout elapses before stability is detected.
    The caller should still proceed in that case — the chart is *probably*
    ready; we just couldn't prove it.
    """
    start = time.monotonic()
    last_bar_count = -1
    stable_count = 0

    while time.monotonic() - start < timeout:
        state = await evaluate(
            """
            (function() {
              var spinner = document.querySelector('[class*="loader"]')
                || document.querySelector('[class*="loading"]')
                || document.querySelector('[data-name="loading"]');
              var isLoading = spinner && spinner.offsetParent !== null;
              var barCount = -1;
              try {
                var bars = document.querySelectorAll('[class*="bar"]');
                barCount = bars.length;
              } catch (e) {}
              var symbolEl = document.querySelector('[data-name="legend-source-title"]')
                || document.querySelector('[class*="title"] [class*="apply-common-tooltip"]');
              var currentSymbol = symbolEl ? symbolEl.textContent.trim() : '';
              return { isLoading: !!isLoading, barCount: barCount, currentSymbol: currentSymbol };
            })()
            """
        )
        if not state:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        if state.get("isLoading"):
            stable_count = 0
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        current_sym = (state.get("currentSymbol") or "").upper()
        if expected_symbol and current_sym and expected_symbol.upper() not in current_sym:
            stable_count = 0
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        bar_count = state.get("barCount", -1)
        if bar_count == last_bar_count and bar_count > 0:
            stable_count += 1
        else:
            stable_count = 0
        last_bar_count = bar_count

        if stable_count >= 2:
            return True

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    return False
