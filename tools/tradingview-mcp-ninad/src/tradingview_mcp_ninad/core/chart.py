"""Core chart-reading and chart-control logic.

Every function runs one or two JS IIFEs inside TradingView's page context via
CDP ``Runtime.evaluate``. Heavy chart introspection is batched into a single
eval to keep latency low — each CDP roundtrip adds ~30 ms on localhost.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from typing import Any

import httpx

from ..connection import evaluate, evaluate_async
from ..connection.api_resolver import KNOWN_PATHS
from .wait import wait_for_chart_ready

CHART_API: str = KNOWN_PATHS["chart_api"]


async def get_state() -> dict[str, Any]:
    """Return the chart's current symbol, resolution, type, and indicator list."""
    state = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var studies = [];
          try {{
            var allStudies = chart.getAllStudies();
            studies = allStudies.map(function(s) {{
              return {{ id: s.id, name: s.name || s.title || 'unknown' }};
            }});
          }} catch(e) {{}}
          return {{
            symbol: chart.symbol(),
            resolution: chart.resolution(),
            chartType: chart.chartType(),
            studies: studies,
          }};
        }})()
        """
    )
    return {"success": True, **(state or {})}


async def set_symbol(*, symbol: str) -> dict[str, Any]:
    """Change the active ticker and wait for the chart to reload."""
    safe_sym = symbol.replace("'", "\\'")
    await evaluate_async(
        f"""
        (function() {{
          var chart = {CHART_API};
          return new Promise(function(resolve) {{
            chart.setSymbol('{safe_sym}', {{}});
            setTimeout(resolve, 500);
          }});
        }})()
        """
    )
    ready = await wait_for_chart_ready(expected_symbol=symbol)
    return {"success": True, "symbol": symbol, "chart_ready": ready}


async def set_timeframe(*, timeframe: str) -> dict[str, Any]:
    """Switch the chart resolution and wait for it to settle."""
    safe_tf = timeframe.replace("'", "\\'")
    await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          chart.setResolution('{safe_tf}', {{}});
        }})()
        """
    )
    ready = await wait_for_chart_ready(expected_timeframe=timeframe)
    return {"success": True, "timeframe": timeframe, "chart_ready": ready}


async def set_type(*, chart_type: str) -> dict[str, Any]:
    """Change the chart rendering style (candles, line, area, …)."""
    type_map = {
        "Bars": 0, "Candles": 1, "Line": 2, "Area": 3,
        "Renko": 4, "Kagi": 5, "PointAndFigure": 6, "LineBreak": 7,
        "HeikinAshi": 8, "HollowCandles": 9,
    }
    type_num = type_map.get(chart_type)
    if type_num is None:
        try:
            type_num = int(chart_type)
        except ValueError:
            raise ValueError(
                f"Unknown chart type: {chart_type}. Use a name (Candles, Line, …) or number (0-9)."
            ) from None
    await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          chart.setChartType({type_num});
        }})()
        """
    )
    return {"success": True, "chart_type": chart_type, "type_num": type_num}


async def manage_indicator(
    *,
    action: str,
    indicator: str,
    entity_id: str | None = None,
    inputs: str | None = None,
) -> dict[str, Any]:
    """Add or remove an indicator on the chart."""
    parsed_inputs = json.loads(inputs) if inputs else None

    if action == "add":
        input_arr = (
            [{"id": k, "value": v} for k, v in parsed_inputs.items()]
            if parsed_inputs
            else []
        )
        safe_ind = indicator.replace("'", "\\'")
        before = await evaluate(
            f"{CHART_API}.getAllStudies().map(function(s) {{ return s.id; }})"
        ) or []
        await evaluate(
            f"""
            (function() {{
              var chart = {CHART_API};
              chart.createStudy('{safe_ind}', false, false, {json.dumps(input_arr)});
            }})()
            """
        )
        await asyncio.sleep(1.5)
        after = await evaluate(
            f"{CHART_API}.getAllStudies().map(function(s) {{ return s.id; }})"
        ) or []
        new_ids = [sid for sid in after if sid not in before]
        return {
            "success": len(new_ids) > 0,
            "action": "add",
            "indicator": indicator,
            "entity_id": new_ids[0] if new_ids else None,
            "new_study_count": len(new_ids),
        }

    if action == "remove":
        if not entity_id:
            raise ValueError(
                "entity_id required for remove action. Use chart_get_state to find study IDs."
            )
        safe_id = entity_id.replace("'", "\\'")
        await evaluate(
            f"""
            (function() {{
              var chart = {CHART_API};
              chart.removeEntity('{safe_id}');
            }})()
            """
        )
        return {"success": True, "action": "remove", "entity_id": entity_id}

    raise ValueError('action must be "add" or "remove"')


async def get_visible_range() -> dict[str, Any]:
    """Return the on-screen date range (unix timestamps) and bar indices."""
    result = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          return {{ visible_range: chart.getVisibleRange(), bars_range: chart.getVisibleBarsRange() }};
        }})()
        """
    ) or {}
    return {
        "success": True,
        "visible_range": result.get("visible_range"),
        "bars_range": result.get("bars_range"),
    }


async def set_visible_range(*, from_ts: float, to_ts: float) -> dict[str, Any]:
    """Zoom the chart to display a specific timestamp window."""
    await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var m = chart._chartWidget.model();
          var ts = m.timeScale();
          var bars = m.mainSeries().bars();
          var startIdx = bars.firstIndex();
          var endIdx = bars.lastIndex();
          var fromIdx = startIdx, toIdx = endIdx;
          for (var i = startIdx; i <= endIdx; i++) {{
            var v = bars.valueAt(i);
            if (v && v[0] >= {from_ts} && fromIdx === startIdx) fromIdx = i;
            if (v && v[0] <= {to_ts}) toIdx = i;
          }}
          ts.zoomToBarsRange(fromIdx, toIdx);
        }})()
        """
    )
    await asyncio.sleep(0.5)
    actual = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          try {{ var r = chart.getVisibleRange(); return {{ from: r.from || 0, to: r.to || 0 }}; }}
          catch(e) {{ return {{ from: 0, to: 0, error: e.message }}; }}
        }})()
        """
    ) or {"from": 0, "to": 0}
    return {
        "success": True,
        "requested": {"from": from_ts, "to": to_ts},
        "actual": actual,
    }


async def scroll_to_date(*, date: str) -> dict[str, Any]:
    """Center the chart viewport on a given date.

    Accepts either an ISO date string (``"2024-01-15"``) or a bare unix
    timestamp as a string. The viewport is sized to show roughly 50 bars
    around the target.
    """
    if date.isdigit():
        timestamp = int(date)
    else:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            timestamp = int(dt.timestamp())
        except ValueError:
            raise ValueError(
                f"Could not parse date: {date}. Use ISO format (2024-01-15) or unix timestamp."
            ) from None

    resolution = await evaluate(f"{CHART_API}.resolution()") or "60"
    res_str = str(resolution)
    if res_str in ("D", "1D"):
        secs_per_bar = 86400
    elif res_str in ("W", "1W"):
        secs_per_bar = 604800
    elif res_str in ("M", "1M"):
        secs_per_bar = 2592000
    else:
        try:
            secs_per_bar = int(res_str) * 60
        except ValueError:
            secs_per_bar = 60

    half_window = 25 * secs_per_bar
    from_ts = timestamp - half_window
    to_ts = timestamp + half_window

    await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var m = chart._chartWidget.model();
          var ts = m.timeScale();
          var bars = m.mainSeries().bars();
          var startIdx = bars.firstIndex();
          var endIdx = bars.lastIndex();
          var fromIdx = startIdx, toIdx = endIdx;
          for (var i = startIdx; i <= endIdx; i++) {{
            var v = bars.valueAt(i);
            if (v && v[0] >= {from_ts} && fromIdx === startIdx) fromIdx = i;
            if (v && v[0] <= {to_ts}) toIdx = i;
          }}
          ts.zoomToBarsRange(fromIdx, toIdx);
        }})()
        """
    )
    await asyncio.sleep(0.5)
    return {
        "success": True,
        "date": date,
        "centered_on": timestamp,
        "resolution": resolution,
        "window": {"from": from_ts, "to": to_ts},
    }


async def symbol_info() -> dict[str, Any]:
    """Return detailed metadata (exchange, type, description) for the active symbol."""
    result = await evaluate(
        f"""
        (function() {{
          var chart = {CHART_API};
          var info = chart.symbolExt();
          return {{
            symbol: info.symbol, full_name: info.full_name, exchange: info.exchange,
            description: info.description, type: info.type, pro_name: info.pro_name,
            typespecs: info.typespecs, resolution: chart.resolution(), chart_type: chart.chartType()
          }};
        }})()
        """
    ) or {}
    return {"success": True, **result}


async def symbol_search(*, query: str, type: str | None = None) -> dict[str, Any]:
    """Search TradingView's public symbol index (REST, no auth required)."""
    params = {
        "text": query,
        "hl": "1",
        "exchange": "",
        "lang": "en",
        "search_type": type or "",
        "domain": "production",
    }
    url = "https://symbol-search.tradingview.com/symbol_search/v3/"
    headers = {
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    def strip_em(s: str) -> str:
        return (s or "").replace("<em>", "").replace("</em>", "")

    raw = data.get("symbols") or data if isinstance(data, list) else data.get("symbols", [])
    results = [
        {
            "symbol": strip_em(r.get("symbol", "")),
            "description": strip_em(r.get("description", "")),
            "exchange": r.get("exchange") or r.get("prefix", ""),
            "type": r.get("type", ""),
            "full_name": (
                f"{r.get('exchange', '')}:{strip_em(r.get('symbol', ''))}"
                if r.get("exchange")
                else strip_em(r.get("symbol", ""))
            ),
        }
        for r in (raw if isinstance(raw, list) else [])[:15]
    ]
    return {
        "success": True,
        "query": query,
        "source": "rest_api",
        "results": results,
        "count": len(results),
    }
