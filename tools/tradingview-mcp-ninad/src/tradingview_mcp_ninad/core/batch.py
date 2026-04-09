"""Core batch execution: run an action across multiple symbols/timeframes."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from typing import Any

import anyio

from ..connection import evaluate, evaluate_async, get_chart_api, get_chart_collection, get_client
from ..logging_config import state_dir
from .wait import wait_for_chart_ready

SCREENSHOT_DIR = state_dir() / "screenshots"


async def batch_run(
    *,
    symbols: list[str],
    timeframes: list[str] | None = None,
    action: str,
    delay_ms: int | None = None,
    ohlcv_count: int | None = None,
) -> dict[str, Any]:
    """Iterate over symbols × timeframes and execute *action* on each combination."""
    tfs = timeframes if timeframes else [None]
    delay = (delay_ms or 2000) / 1000.0
    results: list[dict[str, Any]] = []

    col_path: str | None = None
    api_path: str | None = None
    try:
        col_path = await get_chart_collection()
    except Exception:
        pass
    try:
        api_path = await get_chart_api()
    except Exception:
        pass

    for symbol in symbols:
        for tf in tfs:
            combo: dict[str, Any] = {"symbol": symbol, "timeframe": tf}
            try:
                safe_sym = symbol.replace("'", "\\'")
                if col_path:
                    await evaluate(f"{col_path}.setSymbol('{safe_sym}')")
                elif api_path:
                    await evaluate(f"{api_path}.setSymbol('{safe_sym}')")

                if tf:
                    safe_tf = tf.replace("'", "\\'")
                    if col_path:
                        await evaluate(f"{col_path}.setResolution('{safe_tf}')")
                    elif api_path:
                        await evaluate(f"{api_path}.setResolution('{safe_tf}')")

                await wait_for_chart_ready(expected_symbol=symbol)
                await asyncio.sleep(delay)

                action_result: dict[str, Any]
                if action == "screenshot":
                    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                    tab = await get_client()
                    def _screenshot():
                        return tab.Page.captureScreenshot(format="png")
                    result_raw = await anyio.to_thread.run_sync(_screenshot)
                    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                    fname = f"batch_{symbol}_{tf or 'default'}_{ts}.png"
                    file_path = SCREENSHOT_DIR / fname
                    raw = base64.b64decode(result_raw.get("data", ""))
                    file_path.write_bytes(raw)
                    action_result = {"file_path": str(file_path)}

                elif action == "get_ohlcv" and api_path:
                    limit = min(ohlcv_count or 100, 500)
                    action_result = await evaluate_async(
                        f"""
                        new Promise(function(resolve, reject) {{
                          {api_path}.exportData({{ includeTime: true, includeSeries: true, includeStudies: false }})
                            .then(function(result) {{
                              var bars = (result.data || []).slice(-{limit});
                              resolve({{ bar_count: bars.length, last_bar: bars[bars.length - 1] || null }});
                            }}).catch(reject);
                        }})
                        """
                    ) or {}

                elif action == "get_strategy_results":
                    await asyncio.sleep(1.0)
                    action_result = await evaluate("""
                        (function() {
                          var metrics = {};
                          var panel = document.querySelector('[data-name="backtesting"]') || document.querySelector('[class*="strategyReport"]');
                          if (!panel) return { error: 'Strategy Tester not found' };
                          var items = panel.querySelectorAll('[class*="reportItem"], [class*="metric"]');
                          items.forEach(function(item) {
                            var label = item.querySelector('[class*="label"]');
                            var value = item.querySelector('[class*="value"]');
                            if (label && value) metrics[label.textContent.trim()] = value.textContent.trim();
                          });
                          return { metric_count: Object.keys(metrics).length, metrics: metrics };
                        })()
                    """) or {}
                else:
                    action_result = {"error": f"Unknown action or API not available: {action}"}

                results.append({**combo, "success": True, "result": action_result})
            except Exception as exc:
                results.append({**combo, "success": False, "error": str(exc)})

    success_count = sum(1 for r in results if r.get("success"))
    return {
        "success": True,
        "total_iterations": len(results),
        "successful": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }
