"""Core pane/layout management: multi-chart grid control."""

from __future__ import annotations

import asyncio
from typing import Any

from ..connection import evaluate, evaluate_async

CWC: str = "window.TradingViewApi._chartWidgetCollection"

LAYOUT_NAMES: dict[str, str] = {
    "s": "1 chart", "2h": "2 horizontal", "2v": "2 vertical",
    "2-1": "2 top, 1 bottom", "1-2": "1 top, 2 bottom",
    "3h": "3 horizontal", "3v": "3 vertical", "3s": "3 custom",
    "4": "2x2 grid", "4h": "4 horizontal", "4v": "4 vertical", "4s": "4 custom",
    "6": "6 charts", "8": "8 charts", "10": "10 charts",
    "12": "12 charts", "14": "14 charts", "16": "16 charts",
}

LAYOUT_ALIASES: dict[str, str] = {
    "single": "s", "1": "s", "1x1": "s",
    "2x1": "2h", "1x2": "2v",
    "2x2": "4", "grid": "4", "quad": "4",
    "3x1": "3h", "1x3": "3v",
}


async def list_panes() -> dict[str, Any]:
    result = await evaluate(
        f"""
        (function() {{
          var cwc = {CWC};
          var layoutType = cwc._layoutType;
          if (typeof layoutType === 'object' && layoutType && typeof layoutType.value === 'function') layoutType = layoutType.value();
          var count = cwc.inlineChartsCount;
          if (typeof count === 'object' && count && typeof count.value === 'function') count = count.value();
          var all = cwc.getAll();
          var panes = [];
          for (var i = 0; i < all.length; i++) {{
            try {{
              var c = all[i]; var model = c.model ? c.model() : null;
              var mainSeries = model ? model.mainSeries() : null;
              var sym = mainSeries ? mainSeries.symbol() : 'unknown';
              var res = mainSeries ? mainSeries.interval() : null;
              panes.push({{ index: i, symbol: sym, resolution: res || null }});
            }} catch(e) {{ panes.push({{ index: i, error: e.message }}); }}
          }}
          var activeChart = window.TradingViewApi._activeChartWidgetWV.value();
          var activeIndex = null;
          for (var j = 0; j < all.length; j++) {{
            try {{ if (all[j].model && activeChart._chartWidget && all[j] === activeChart._chartWidget) {{ activeIndex = j; break; }} }} catch(e) {{}}
          }}
          return {{ layout: layoutType, chart_count: count, active_index: activeIndex, panes: panes }};
        }})()
        """
    ) or {}
    layout = result.get("layout", "s")
    return {
        "success": True,
        "layout": layout,
        "layout_name": LAYOUT_NAMES.get(str(layout), str(layout)),
        "chart_count": result.get("chart_count"),
        "active_index": result.get("active_index"),
        "panes": result.get("panes", []),
    }


async def set_layout(*, layout: str) -> dict[str, Any]:
    code = layout.lower().strip()
    resolved = LAYOUT_ALIASES.get(code, code)
    if resolved not in LAYOUT_NAMES:
        available = "\n".join(f"  {k} — {v}" for k, v in LAYOUT_NAMES.items())
        raise ValueError(f'Unknown layout "{layout}". Available layouts:\n{available}')
    await evaluate_async(f"{CWC}.setLayout('{resolved}')")
    await asyncio.sleep(0.5)
    state = await list_panes()
    return {
        "success": True,
        "layout": resolved,
        "layout_name": LAYOUT_NAMES[resolved],
        "chart_count": state.get("chart_count"),
        "panes": state.get("panes"),
    }


async def focus(*, index: int) -> dict[str, Any]:
    result = await evaluate(
        f"""
        (function() {{
          var cwc = {CWC};
          var all = cwc.getAll();
          if ({index} >= all.length) return {{ error: 'Pane index {index} out of range (have ' + all.length + ' panes)' }};
          var chart = all[{index}];
          if (chart._mainDiv) chart._mainDiv.click();
          return {{ focused: {index}, total: all.length }};
        }})()
        """
    )
    if result and result.get("error"):
        raise RuntimeError(result["error"])
    return {"success": True, "focused_index": (result or {}).get("focused"), "total_panes": (result or {}).get("total")}


async def set_symbol(*, index: int, symbol: str) -> dict[str, Any]:
    await focus(index=index)
    await asyncio.sleep(0.3)
    safe_sym = symbol.replace("'", "\\'")
    await evaluate_async(
        f"""
        (function() {{
          var chart = window.TradingViewApi._activeChartWidgetWV.value();
          return new Promise(function(resolve) {{
            chart.setSymbol('{safe_sym}', {{}});
            setTimeout(resolve, 500);
          }});
        }})()
        """
    )
    return {"success": True, "index": index, "symbol": symbol}
