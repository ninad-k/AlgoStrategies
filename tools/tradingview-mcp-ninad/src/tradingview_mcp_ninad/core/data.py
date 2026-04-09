"""Core data-access logic: OHLCV, indicators, strategy results, quotes, Pine drawings.

The heavy lifting is done in JS IIFEs evaluated inside TradingView's page
context. Python's job is parameter validation, response shaping, and the
summary-mode post-processing that flattens hundreds of bars into a handful
of stats.

The ``buildGraphicsJS`` factory (ported from the original ``_format.js``)
generates JS that walks the internal graphics collection on every Pine study
visible on the chart. The collection key names (``dwglines``, ``dwglabels``,
``dwgtablecells``, ``dwgboxes``) are TradingView internals — they match the
CSS classes the renderer creates, which is how the original project discovered
them.
"""

from __future__ import annotations

from typing import Any

from ..connection import evaluate
from ..connection.api_resolver import KNOWN_PATHS

MAX_OHLCV_BARS: int = 500
MAX_TRADES: int = 20
CHART_API: str = KNOWN_PATHS["chart_api"]
BARS_PATH: str = KNOWN_PATHS["main_series_bars"]


def _build_graphics_js(collection_name: str, map_key: str, study_filter: str) -> str:
    """Return a JS IIFE that extracts Pine drawing primitives from all sources.

    The generated code mirrors the original ``buildGraphicsJS`` helper
    exactly — same property paths, same fallback for ``dwgtablecells``.
    """
    safe_filter = study_filter.replace("'", "\\'")
    return f"""
    (function() {{
      var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
      var model = chart.model();
      var sources = model.model().dataSources();
      var results = [];
      var filter = '{safe_filter}';
      for (var si = 0; si < sources.length; si++) {{
        var s = sources[si];
        if (!s.metaInfo) continue;
        try {{
          var meta = s.metaInfo();
          var name = meta.description || meta.shortDescription || '';
          if (!name) continue;
          if (filter && name.indexOf(filter) === -1) continue;
          var g = s._graphics;
          if (!g || !g._primitivesCollection) continue;
          var pc = g._primitivesCollection;
          var items = [];
          try {{
            var outer = pc.{collection_name};
            if (outer) {{
              var inner = outer.get('{map_key}');
              if (inner) {{
                var coll = inner.get(false);
                if (coll && coll._primitivesDataById && coll._primitivesDataById.size > 0) {{
                  coll._primitivesDataById.forEach(function(v, id) {{ items.push({{id: id, raw: v}}); }});
                }}
              }}
            }}
          }} catch(e) {{}}
          if (items.length === 0 && '{collection_name}' === 'dwgtablecells') {{
            try {{
              var tcOuter = pc.dwgtablecells;
              if (tcOuter) {{
                var tcColl = tcOuter.get('tableCells');
                if (tcColl && tcColl._primitivesDataById && tcColl._primitivesDataById.size > 0) {{
                  tcColl._primitivesDataById.forEach(function(v, id) {{ items.push({{id: id, raw: v}}); }});
                }}
              }}
            }} catch(e) {{}}
          }}
          if (items.length > 0) results.push({{name: name, count: items.length, items: items}});
        }} catch(e) {{}}
      }}
      return results;
    }})()
    """


# ── OHLCV ────────────────────────────────────────────────────────────────────


async def get_ohlcv(
    *,
    count: int | None = None,
    summary: bool | None = None,
) -> dict[str, Any]:
    """Fetch OHLCV bars and optionally reduce them to summary stats."""
    limit = min(count or 100, MAX_OHLCV_BARS)
    data = await evaluate(
        f"""
        (function() {{
          var bars = {BARS_PATH};
          if (!bars || typeof bars.lastIndex !== 'function') return null;
          var result = [];
          var end = bars.lastIndex();
          var start = Math.max(bars.firstIndex(), end - {limit} + 1);
          for (var i = start; i <= end; i++) {{
            var v = bars.valueAt(i);
            if (v) result.push({{time: v[0], open: v[1], high: v[2], low: v[3], close: v[4], volume: v[5] || 0}});
          }}
          return {{bars: result, total_bars: bars.size(), source: 'direct_bars'}};
        }})()
        """
    )
    if not data or not data.get("bars"):
        raise RuntimeError("Could not extract OHLCV data. The chart may still be loading.")

    bars: list[dict[str, Any]] = data["bars"]
    if not bars:
        raise RuntimeError("Could not extract OHLCV data. The chart may still be loading.")

    if summary:
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        volumes = [b["volume"] for b in bars]
        first, last = bars[0], bars[-1]
        change = round(last["close"] - first["open"], 2)
        change_pct = round((change / first["open"]) * 100, 2) if first["open"] else 0
        return {
            "success": True,
            "bar_count": len(bars),
            "period": {"from": first["time"], "to": last["time"]},
            "open": first["open"],
            "close": last["close"],
            "high": max(highs),
            "low": min(lows),
            "range": round(max(highs) - min(lows), 2),
            "change": change,
            "change_pct": f"{change_pct}%",
            "avg_volume": round(sum(volumes) / len(volumes)) if volumes else 0,
            "last_5_bars": bars[-5:],
        }

    return {
        "success": True,
        "bar_count": len(bars),
        "total_available": data.get("total_bars"),
        "source": data.get("source"),
        "bars": bars,
    }


# ── Single indicator info ────────────────────────────────────────────────────


async def get_indicator(*, entity_id: str) -> dict[str, Any]:
    """Return visibility and input values for one specific indicator."""
    safe_id = entity_id.replace("'", "\\'")
    data = await evaluate(
        f"""
        (function() {{
          var api = {CHART_API};
          var study = api.getStudyById('{safe_id}');
          if (!study) return {{ error: 'Study not found: {safe_id}' }};
          var result = {{ name: null, inputs: null, visible: null }};
          try {{ result.visible = study.isVisible(); }} catch(e) {{}}
          try {{ result.inputs = study.getInputValues(); }} catch(e) {{ result.inputs_error = e.message; }}
          return result;
        }})()
        """
    )
    if data and data.get("error"):
        raise RuntimeError(data["error"])

    inputs = (data or {}).get("inputs")
    if isinstance(inputs, list):
        inputs = [
            inp for inp in inputs
            if not (inp.get("id") == "text" and isinstance(inp.get("value"), str) and len(inp["value"]) > 200)
            and not (isinstance(inp.get("value"), str) and len(inp["value"]) > 500)
        ]
    return {
        "success": True,
        "entity_id": entity_id,
        "visible": (data or {}).get("visible"),
        "inputs": inputs,
    }


# ── Strategy Tester ──────────────────────────────────────────────────────────


async def get_strategy_results() -> dict[str, Any]:
    """Read aggregated metrics from the Strategy Tester panel."""
    results = await evaluate(
        f"""
        (function() {{
          try {{
            var chart = {CHART_API}._chartWidget;
            var sources = chart.model().model().dataSources();
            var strat = null;
            for (var i = 0; i < sources.length; i++) {{
              var s = sources[i];
              if (s.metaInfo && s.metaInfo().is_price_study === false && (s.reportData || s.performance)) {{ strat = s; break; }}
            }}
            if (!strat) return {{metrics: {{}}, source: 'internal_api', error: 'No strategy found on chart. Add a strategy indicator first.'}};
            var metrics = {{}};
            if (strat.reportData) {{
              var rd = typeof strat.reportData === 'function' ? strat.reportData() : strat.reportData;
              if (rd && typeof rd === 'object') {{
                if (typeof rd.value === 'function') rd = rd.value();
                if (rd) {{ var keys = Object.keys(rd); for (var k = 0; k < keys.length; k++) {{ var val = rd[keys[k]]; if (val !== null && val !== undefined && typeof val !== 'function') metrics[keys[k]] = val; }} }}
              }}
            }}
            if (Object.keys(metrics).length === 0 && strat.performance) {{
              var perf = strat.performance();
              if (perf && typeof perf.value === 'function') perf = perf.value();
              if (perf && typeof perf === 'object') {{ var pkeys = Object.keys(perf); for (var p = 0; p < pkeys.length; p++) {{ var pval = perf[pkeys[p]]; if (pval !== null && pval !== undefined && typeof pval !== 'function') metrics[pkeys[p]] = pval; }} }}
            }}
            return {{metrics: metrics, source: 'internal_api'}};
          }} catch(e) {{ return {{metrics: {{}}, source: 'internal_api', error: e.message}}; }}
        }})()
        """
    ) or {}
    metrics = results.get("metrics") or {}
    return {
        "success": True,
        "metric_count": len(metrics),
        "source": results.get("source"),
        "metrics": metrics,
        "error": results.get("error"),
    }


async def get_trades(*, max_trades: int | None = None) -> dict[str, Any]:
    """List individual trades from the Strategy Tester."""
    limit = min(max_trades or 20, MAX_TRADES)
    trades = await evaluate(
        f"""
        (function() {{
          try {{
            var chart = {CHART_API}._chartWidget;
            var sources = chart.model().model().dataSources();
            var strat = null;
            for (var i = 0; i < sources.length; i++) {{
              var s = sources[i];
              if (s.metaInfo && s.metaInfo().is_price_study === false && (s.ordersData || s.reportData)) {{ strat = s; break; }}
            }}
            if (!strat) return {{trades: [], source: 'internal_api', error: 'No strategy found on chart.'}};
            var orders = null;
            if (strat.ordersData) {{ orders = typeof strat.ordersData === 'function' ? strat.ordersData() : strat.ordersData; if (orders && typeof orders.value === 'function') orders = orders.value(); }}
            if (!orders || !Array.isArray(orders)) {{
              if (strat._orders) orders = strat._orders;
              else if (strat.tradesData) {{ orders = typeof strat.tradesData === 'function' ? strat.tradesData() : strat.tradesData; if (orders && typeof orders.value === 'function') orders = orders.value(); }}
            }}
            if (!orders || !Array.isArray(orders)) return {{trades: [], source: 'internal_api', error: 'ordersData() returned non-array.'}};
            var result = [];
            for (var t = 0; t < Math.min(orders.length, {limit}); t++) {{
              var o = orders[t];
              if (typeof o === 'object' && o !== null) {{
                var trade = {{}};
                var okeys = Object.keys(o);
                for (var k = 0; k < okeys.length; k++) {{ var v = o[okeys[k]]; if (v !== null && v !== undefined && typeof v !== 'function' && typeof v !== 'object') trade[okeys[k]] = v; }}
                result.push(trade);
              }}
            }}
            return {{trades: result, source: 'internal_api'}};
          }} catch(e) {{ return {{trades: [], source: 'internal_api', error: e.message}}; }}
        }})()
        """
    ) or {}
    return {
        "success": True,
        "trade_count": len(trades.get("trades") or []),
        "source": trades.get("source"),
        "trades": trades.get("trades", []),
        "error": trades.get("error"),
    }


async def get_equity() -> dict[str, Any]:
    """Retrieve the equity curve from the Strategy Tester."""
    equity = await evaluate(
        f"""
        (function() {{
          try {{
            var chart = {CHART_API}._chartWidget;
            var sources = chart.model().model().dataSources();
            var strat = null;
            for (var i = 0; i < sources.length; i++) {{
              var s = sources[i];
              if (s.metaInfo && s.metaInfo().is_price_study === false && (s.reportData || s.performance)) {{ strat = s; break; }}
            }}
            if (!strat) return {{data: [], source: 'internal_api', error: 'No strategy found on chart.'}};
            var data = [];
            if (strat.equityData) {{
              var eq = typeof strat.equityData === 'function' ? strat.equityData() : strat.equityData;
              if (eq && typeof eq.value === 'function') eq = eq.value();
              if (Array.isArray(eq)) data = eq;
            }}
            if (data.length === 0 && strat.bars) {{
              var bars = typeof strat.bars === 'function' ? strat.bars() : strat.bars;
              if (bars && typeof bars.lastIndex === 'function') {{
                var end = bars.lastIndex(); var start = bars.firstIndex();
                for (var i = start; i <= end; i++) {{ var v = bars.valueAt(i); if (v) data.push({{time: v[0], equity: v[1], drawdown: v[2] || null}}); }}
              }}
            }}
            if (data.length === 0) {{
              var perfData = {{}};
              if (strat.performance) {{
                var perf = strat.performance();
                if (perf && typeof perf.value === 'function') perf = perf.value();
                if (perf && typeof perf === 'object') {{ var pkeys = Object.keys(perf); for (var p = 0; p < pkeys.length; p++) {{ if (/equity|drawdown|profit|net/i.test(pkeys[p])) perfData[pkeys[p]] = perf[pkeys[p]]; }} }}
              }}
              if (Object.keys(perfData).length > 0) return {{data: [], equity_summary: perfData, source: 'internal_api', note: 'Full equity curve not available via API; equity summary metrics returned instead.'}};
            }}
            return {{data: data, source: 'internal_api'}};
          }} catch(e) {{ return {{data: [], source: 'internal_api', error: e.message}}; }}
        }})()
        """
    ) or {}
    return {
        "success": True,
        "data_points": len(equity.get("data") or []),
        "source": equity.get("source"),
        "data": equity.get("data", []),
        "equity_summary": equity.get("equity_summary"),
        "note": equity.get("note"),
        "error": equity.get("error"),
    }


# ── Quote / Depth ────────────────────────────────────────────────────────────


async def get_quote(*, symbol: str | None = None) -> dict[str, Any]:
    """Snapshot the latest price (last, OHLC, volume) from bars + DOM."""
    safe_sym = (symbol or "").replace("'", "\\'")
    data = await evaluate(
        f"""
        (function() {{
          var api = {CHART_API};
          var sym = '{safe_sym}';
          if (!sym) {{ try {{ sym = api.symbol(); }} catch(e) {{}} }}
          if (!sym) {{ try {{ sym = api.symbolExt().symbol; }} catch(e) {{}} }}
          var ext = {{}};
          try {{ ext = api.symbolExt() || {{}}; }} catch(e) {{}}
          var bars = {BARS_PATH};
          var quote = {{ symbol: sym }};
          if (bars && typeof bars.lastIndex === 'function') {{
            var last = bars.valueAt(bars.lastIndex());
            if (last) {{ quote.time = last[0]; quote.open = last[1]; quote.high = last[2]; quote.low = last[3]; quote.close = last[4]; quote.last = last[4]; quote.volume = last[5] || 0; }}
          }}
          try {{
            var bidEl = document.querySelector('[class*="bid"] [class*="price"], [class*="dom-"] [class*="bid"]');
            var askEl = document.querySelector('[class*="ask"] [class*="price"], [class*="dom-"] [class*="ask"]');
            if (bidEl) quote.bid = parseFloat(bidEl.textContent.replace(/[^0-9.\\-]/g, ''));
            if (askEl) quote.ask = parseFloat(askEl.textContent.replace(/[^0-9.\\-]/g, ''));
          }} catch(e) {{}}
          try {{
            var hdr = document.querySelector('[class*="headerRow"] [class*="last-"]');
            if (hdr) {{ var hdrPrice = parseFloat(hdr.textContent.replace(/[^0-9.\\-]/g, '')); if (!isNaN(hdrPrice)) quote.header_price = hdrPrice; }}
          }} catch(e) {{}}
          if (ext.description) quote.description = ext.description;
          if (ext.exchange) quote.exchange = ext.exchange;
          if (ext.type) quote.type = ext.type;
          return quote;
        }})()
        """
    )
    if not data or (not data.get("last") and not data.get("close")):
        raise RuntimeError("Could not retrieve quote. The chart may still be loading.")
    return {"success": True, **data}


async def get_depth() -> dict[str, Any]:
    """Read the DOM / order-book panel for bid/ask levels and spread."""
    data = await evaluate(
        """
        (function() {
          var domPanel = document.querySelector('[class*="depth"]')
            || document.querySelector('[class*="orderBook"]')
            || document.querySelector('[class*="dom-"]')
            || document.querySelector('[class*="DOM"]')
            || document.querySelector('[data-name="dom"]');
          if (!domPanel) return { found: false, error: 'DOM / Depth of Market panel not found.' };
          var bids = [], asks = [];
          var rows = domPanel.querySelectorAll('[class*="row"], tr');
          for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var priceEl = row.querySelector('[class*="price"]');
            var sizeEl = row.querySelector('[class*="size"], [class*="volume"], [class*="qty"]');
            if (!priceEl) continue;
            var price = parseFloat(priceEl.textContent.replace(/[^0-9.\\-]/g, ''));
            var size = sizeEl ? parseFloat(sizeEl.textContent.replace(/[^0-9.\\-]/g, '')) : 0;
            if (isNaN(price)) continue;
            var rowClass = row.className || '';
            var rowHTML = row.innerHTML || '';
            if (/bid|buy/i.test(rowClass) || /bid|buy/i.test(rowHTML)) bids.push({ price: price, size: size });
            else if (/ask|sell/i.test(rowClass) || /ask|sell/i.test(rowHTML)) asks.push({ price: price, size: size });
            else if (i < rows.length / 2) asks.push({ price: price, size: size });
            else bids.push({ price: price, size: size });
          }
          if (bids.length === 0 && asks.length === 0) {
            var cells = domPanel.querySelectorAll('[class*="cell"], td');
            var prices = [];
            cells.forEach(function(c) { var val = parseFloat(c.textContent.replace(/[^0-9.\\-]/g, '')); if (!isNaN(val) && val > 0) prices.push(val); });
            if (prices.length > 0) return { found: true, raw_values: prices.slice(0, 50), bids: [], asks: [], note: 'Could not classify bid/ask levels.' };
          }
          bids.sort(function(a, b) { return b.price - a.price; });
          asks.sort(function(a, b) { return a.price - b.price; });
          var spread = null;
          if (asks.length > 0 && bids.length > 0) spread = +(asks[0].price - bids[0].price).toFixed(6);
          return { found: true, bids: bids, asks: asks, spread: spread };
        })()
        """
    )
    if not data or not data.get("found"):
        raise RuntimeError(
            (data or {}).get("error", "DOM panel not found.")
        )
    return {
        "success": True,
        "bid_levels": len(data.get("bids") or []),
        "ask_levels": len(data.get("asks") or []),
        "spread": data.get("spread"),
        "bids": data.get("bids", []),
        "asks": data.get("asks", []),
        "raw_values": data.get("raw_values"),
        "note": data.get("note"),
    }


# ── Study values (data window readout) ──────────────────────────────────────


async def get_study_values() -> dict[str, Any]:
    """Read the Data Window's indicator readout for every visible study."""
    data = await evaluate(
        """
        (function() {
          var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
          var model = chart.model();
          var sources = model.model().dataSources();
          var results = [];
          for (var si = 0; si < sources.length; si++) {
            var s = sources[si];
            if (!s.metaInfo) continue;
            try {
              var meta = s.metaInfo();
              var name = meta.description || meta.shortDescription || '';
              if (!name) continue;
              var values = {};
              try {
                var dwv = s.dataWindowView();
                if (dwv) {
                  var items = dwv.items();
                  if (items) {
                    for (var i = 0; i < items.length; i++) {
                      var item = items[i];
                      if (item._value && item._value !== '∅' && item._title)
                        values[item._title] = item._value;
                    }
                  }
                }
              } catch(e) {}
              if (Object.keys(values).length > 0)
                results.push({ name: name, values: values });
            } catch(e) {}
          }
          return results;
        })()
        """
    )
    return {"success": True, "study_count": len(data or []), "studies": data or []}


# ── Pine drawing readers ─────────────────────────────────────────────────────


async def get_pine_lines(
    *,
    study_filter: str | None = None,
    verbose: bool | None = None,
) -> dict[str, Any]:
    """Extract line.new drawings from visible Pine indicators."""
    raw = await evaluate(_build_graphics_js("dwglines", "lines", study_filter or ""))
    if not raw:
        return {"success": True, "study_count": 0, "studies": []}

    studies = []
    for s in raw:
        h_levels: list[float] = []
        seen: set[float] = set()
        all_lines: list[dict[str, Any]] = []
        for item in s.get("items", []):
            v = item.get("raw", {})
            y1 = round(v["y1"], 2) if v.get("y1") is not None else None
            y2 = round(v["y2"], 2) if v.get("y2") is not None else None
            if verbose:
                all_lines.append({
                    "id": item.get("id"),
                    "y1": y1, "y2": y2,
                    "x1": v.get("x1"), "x2": v.get("x2"),
                    "horizontal": v.get("y1") == v.get("y2"),
                    "style": v.get("st"),
                    "width": v.get("w"),
                    "color": v.get("ci"),
                })
            if y1 is not None and v.get("y1") == v.get("y2") and y1 not in seen:
                h_levels.append(y1)
                seen.add(y1)
        h_levels.sort(reverse=True)
        entry: dict[str, Any] = {
            "name": s.get("name"),
            "total_lines": s.get("count"),
            "horizontal_levels": h_levels,
        }
        if verbose:
            entry["all_lines"] = all_lines
        studies.append(entry)
    return {"success": True, "study_count": len(studies), "studies": studies}


async def get_pine_labels(
    *,
    study_filter: str | None = None,
    max_labels: int | None = None,
    verbose: bool | None = None,
) -> dict[str, Any]:
    """Extract label.new annotations from visible Pine indicators."""
    raw = await evaluate(_build_graphics_js("dwglabels", "labels", study_filter or ""))
    if not raw:
        return {"success": True, "study_count": 0, "studies": []}

    limit = max_labels or 50
    studies = []
    for s in raw:
        labels = []
        for item in s.get("items", []):
            v = item.get("raw", {})
            text = v.get("t", "")
            price = round(v["y"], 2) if v.get("y") is not None else None
            if verbose:
                labels.append({
                    "id": item.get("id"),
                    "text": text, "price": price,
                    "x": v.get("x"), "yloc": v.get("yl"),
                    "size": v.get("sz"),
                    "textColor": v.get("tci"), "color": v.get("ci"),
                })
            elif text or price is not None:
                labels.append({"text": text, "price": price})
        if len(labels) > limit:
            labels = labels[-limit:]
        studies.append({
            "name": s.get("name"),
            "total_labels": s.get("count"),
            "showing": len(labels),
            "labels": labels,
        })
    return {"success": True, "study_count": len(studies), "studies": studies}


async def get_pine_tables(*, study_filter: str | None = None) -> dict[str, Any]:
    """Extract table.new content from visible Pine indicators."""
    raw = await evaluate(
        _build_graphics_js("dwgtablecells", "tableCells", study_filter or "")
    )
    if not raw:
        return {"success": True, "study_count": 0, "studies": []}

    studies = []
    for s in raw:
        tables_map: dict[int, dict[int, dict[int, str]]] = {}
        for item in s.get("items", []):
            v = item.get("raw", {})
            tid = v.get("tid", 0)
            row = v.get("row", 0)
            col = v.get("col", 0)
            tables_map.setdefault(tid, {}).setdefault(row, {})[col] = v.get("t", "")
        table_list = []
        for _tid, rows in sorted(tables_map.items()):
            formatted = []
            for rn in sorted(rows):
                cols = rows[rn]
                line = " | ".join(cols[cn] for cn in sorted(cols) if cols[cn])
                if line:
                    formatted.append(line)
            table_list.append({"rows": formatted})
        studies.append({"name": s.get("name"), "tables": table_list})
    return {"success": True, "study_count": len(studies), "studies": studies}


async def get_pine_boxes(
    *,
    study_filter: str | None = None,
    verbose: bool | None = None,
) -> dict[str, Any]:
    """Extract box.new zones from visible Pine indicators."""
    raw = await evaluate(_build_graphics_js("dwgboxes", "boxes", study_filter or ""))
    if not raw:
        return {"success": True, "study_count": 0, "studies": []}

    studies = []
    for s in raw:
        zones: list[dict[str, float]] = []
        seen: set[str] = set()
        all_boxes: list[dict[str, Any]] = []
        for item in s.get("items", []):
            v = item.get("raw", {})
            y1 = v.get("y1")
            y2 = v.get("y2")
            if y1 is not None and y2 is not None:
                high = round(max(y1, y2), 2)
                low = round(min(y1, y2), 2)
            else:
                high = low = None
            if verbose:
                all_boxes.append({
                    "id": item.get("id"),
                    "high": high, "low": low,
                    "x1": v.get("x1"), "x2": v.get("x2"),
                    "borderColor": v.get("c"), "bgColor": v.get("bc"),
                })
            if high is not None and low is not None:
                key = f"{high}:{low}"
                if key not in seen:
                    zones.append({"high": high, "low": low})
                    seen.add(key)
        zones.sort(key=lambda z: z["high"], reverse=True)
        entry: dict[str, Any] = {
            "name": s.get("name"),
            "total_boxes": s.get("count"),
            "zones": zones,
        }
        if verbose:
            entry["all_boxes"] = all_boxes
        studies.append(entry)
    return {"success": True, "study_count": len(studies), "studies": studies}
