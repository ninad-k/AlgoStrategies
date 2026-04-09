"""Connectivity, API discovery, UI inspection, and TradingView launch logic.

The four public coroutines mirror the JS ``core/health.js`` module:

* :func:`health_check` — proves CDP is alive and the active chart responds
* :func:`discover` — enumerates which internal TradingView APIs are reachable
* :func:`ui_state` — snapshots which panels and buttons are currently visible
* :func:`launch` — starts the TradingView Desktop binary with CDP enabled

The implementations push *all* of the chart introspection into single
``Runtime.evaluate`` calls. Doing the work in JS means one CDP roundtrip
instead of dozens, which is the difference between a sub-second response and
a perceptibly laggy tool.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

from ..connection import evaluate, get_client, get_target_info


async def health_check() -> dict[str, Any]:
    """Verify CDP is reachable and return a snapshot of the active chart.

    Mirrors the JS implementation: connect, fetch target metadata, then run
    a JS IIFE that probes the chart widget and reports symbol/resolution.
    The IIFE swallows its own exceptions so a chartless tab still produces
    a useful payload instead of bubbling a CDP error.
    """
    await get_client()
    target = await get_target_info() or {}

    state = await evaluate(
        """
        (function() {
          var result = { url: window.location.href, title: document.title };
          try {
            var chart = window.TradingViewApi._activeChartWidgetWV.value();
            result.symbol = chart.symbol();
            result.resolution = chart.resolution();
            result.chartType = chart.chartType();
            result.apiAvailable = true;
          } catch (e) {
            result.symbol = 'unknown';
            result.resolution = 'unknown';
            result.chartType = null;
            result.apiAvailable = false;
            result.apiError = e.message;
          }
          return result;
        })()
        """
    )
    state = state or {}

    return {
        "success": True,
        "cdp_connected": True,
        "target_id": target.get("id"),
        "target_url": target.get("url"),
        "target_title": target.get("title"),
        "chart_symbol": state.get("symbol", "unknown"),
        "chart_resolution": state.get("resolution", "unknown"),
        "chart_type": state.get("chartType"),
        "api_available": bool(state.get("apiAvailable", False)),
    }


async def discover() -> dict[str, Any]:
    """Enumerate which TradingView internal API surfaces are reachable.

    Lists each known global, walks its members for callable methods, and
    returns the first 50/30/20 method names so the caller can see what's
    actually wired up without flooding the response.
    """
    paths = await evaluate(
        """
        (function() {
          var results = {};
          try {
            var chart = window.TradingViewApi._activeChartWidgetWV.value();
            var methods = [];
            for (var k in chart) { if (typeof chart[k] === 'function') methods.push(k); }
            results.chartApi = {
              available: true,
              path: 'window.TradingViewApi._activeChartWidgetWV.value()',
              methodCount: methods.length,
              methods: methods.slice(0, 50)
            };
          } catch (e) { results.chartApi = { available: false, error: e.message }; }
          try {
            var col = window.TradingViewApi._chartWidgetCollection;
            var colMethods = [];
            for (var k in col) { if (typeof col[k] === 'function') colMethods.push(k); }
            results.chartWidgetCollection = {
              available: !!col,
              path: 'window.TradingViewApi._chartWidgetCollection',
              methodCount: colMethods.length,
              methods: colMethods.slice(0, 30)
            };
          } catch (e) { results.chartWidgetCollection = { available: false, error: e.message }; }
          try {
            var ws = window.ChartApiInstance;
            var wsMethods = [];
            for (var k in ws) { if (typeof ws[k] === 'function') wsMethods.push(k); }
            results.chartApiInstance = {
              available: !!ws,
              path: 'window.ChartApiInstance',
              methodCount: wsMethods.length,
              methods: wsMethods.slice(0, 30)
            };
          } catch (e) { results.chartApiInstance = { available: false, error: e.message }; }
          try {
            var bwb = window.TradingView && window.TradingView.bottomWidgetBar;
            var bwbMethods = [];
            if (bwb) { for (var k in bwb) { if (typeof bwb[k] === 'function') bwbMethods.push(k); } }
            results.bottomWidgetBar = {
              available: !!bwb,
              path: 'window.TradingView.bottomWidgetBar',
              methodCount: bwbMethods.length,
              methods: bwbMethods.slice(0, 20)
            };
          } catch (e) { results.bottomWidgetBar = { available: false, error: e.message }; }
          try {
            var replay = window.TradingViewApi._replayApi;
            results.replayApi = { available: !!replay, path: 'window.TradingViewApi._replayApi' };
          } catch (e) { results.replayApi = { available: false, error: e.message }; }
          try {
            var alerts = window.TradingViewApi._alertService;
            results.alertService = { available: !!alerts, path: 'window.TradingViewApi._alertService' };
          } catch (e) { results.alertService = { available: false, error: e.message }; }
          return results;
        })()
        """
    )
    paths = paths or {}
    available = sum(1 for v in paths.values() if isinstance(v, dict) and v.get("available"))
    return {
        "success": True,
        "apis_available": available,
        "apis_total": len(paths),
        "apis": paths,
    }


async def ui_state() -> dict[str, Any]:
    """Inspect the DOM to report which TradingView panels are open.

    The big JS blob is a single page traversal: it measures container sizes,
    fingerprints visible buttons, classifies them by screen region, and
    finally pulls a few key chart facts. Pulling everything in one eval keeps
    the picture consistent — TradingView animates panel transitions, so
    multiple smaller calls would race against the layout.
    """
    state = await evaluate(
        """
        (function() {
          var ui = {};
          var bottom = document.querySelector('[class*="layout__area--bottom"]');
          ui.bottom_panel = {
            open: !!(bottom && bottom.offsetHeight > 50),
            height: bottom ? bottom.offsetHeight : 0
          };
          var right = document.querySelector('[class*="layout__area--right"]');
          ui.right_panel = {
            open: !!(right && right.offsetWidth > 50),
            width: right ? right.offsetWidth : 0
          };
          var monacoEl = document.querySelector('.monaco-editor.pine-editor-monaco');
          ui.pine_editor = {
            open: !!monacoEl,
            width: monacoEl ? monacoEl.offsetWidth : 0,
            height: monacoEl ? monacoEl.offsetHeight : 0
          };
          var stratPanel = document.querySelector('[data-name="backtesting"]')
            || document.querySelector('[class*="strategyReport"]');
          ui.strategy_tester = { open: !!(stratPanel && stratPanel.offsetParent) };
          var widgetbar = document.querySelector('[data-name="widgetbar-wrap"]');
          ui.widgetbar = { open: !!(widgetbar && widgetbar.offsetWidth > 50) };
          ui.buttons = {};
          var btns = document.querySelectorAll('button');
          var seen = {};
          for (var i = 0; i < btns.length; i++) {
            var b = btns[i];
            if (b.offsetParent === null || b.offsetWidth < 15) continue;
            var text = b.textContent.trim();
            var aria = b.getAttribute('aria-label') || '';
            var dn = b.getAttribute('data-name') || '';
            var label = text || aria || dn;
            if (!label || label.length > 60) continue;
            var key = label.replace(/[^a-zA-Z0-9 ]/g, '').substring(0, 40);
            if (seen[key]) continue;
            seen[key] = true;
            var rect = b.getBoundingClientRect();
            var region = 'other';
            if (rect.y < 50) region = 'top_bar';
            else if (rect.y < 90 && rect.x < 650) region = 'toolbar';
            else if (rect.x < 45) region = 'left_sidebar';
            else if (rect.x > 650 && rect.y < 100) region = 'pine_header';
            else if (rect.y > 750) region = 'bottom_bar';
            if (!ui.buttons[region]) ui.buttons[region] = [];
            ui.buttons[region].push({
              label: label.substring(0, 40),
              disabled: b.disabled,
              x: Math.round(rect.x),
              y: Math.round(rect.y)
            });
          }
          ui.key_buttons = {};
          var keyLabels = {
            'add_to_chart': /add to chart/i,
            'save_and_add': /save and add/i,
            'update_on_chart': /update on chart/i,
            'save': /^Save(Save)?$/,
            'saved': /^Saved/,
            'publish_script': /publish script/i,
            'compile_errors': /error/i,
            'unsaved_version': /unsaved version/i
          };
          for (var i = 0; i < btns.length; i++) {
            var b = btns[i];
            if (b.offsetParent === null) continue;
            var text = b.textContent.trim();
            for (var k in keyLabels) {
              if (keyLabels[k].test(text)) {
                ui.key_buttons[k] = {
                  text: text.substring(0, 40),
                  disabled: b.disabled,
                  visible: b.offsetWidth > 0
                };
              }
            }
          }
          try {
            var chart = window.TradingViewApi._activeChartWidgetWV.value();
            ui.chart = {
              symbol: chart.symbol(),
              resolution: chart.resolution(),
              chartType: chart.chartType(),
              study_count: chart.getAllStudies().length
            };
          } catch (e) { ui.chart = { error: e.message }; }
          try {
            var replay = window.TradingViewApi._replayApi;
            function unwrap(v) {
              return (v && typeof v === 'object' && typeof v.value === 'function')
                ? v.value() : v;
            }
            ui.replay = {
              available: unwrap(replay.isReplayAvailable()),
              started: unwrap(replay.isReplayStarted())
            };
          } catch (e) { ui.replay = { error: e.message }; }
          return ui;
        })()
        """
    )
    state = state or {}
    return {"success": True, **state}


async def launch(
    *,
    port: int | None = None,
    kill_existing: bool | None = None,
) -> dict[str, Any]:
    """Locate the TradingView Desktop binary and start it with CDP enabled.

    The candidate paths are deliberately platform-specific. We probe each
    well-known location, fall back to ``which``/``where``, and (on macOS) to
    ``mdfind`` so the helper still works on machines that installed
    TradingView under ``~/Applications``. Once a binary is found we
    optionally kill any running instance, spawn a new one with the debug
    flag, and poll the CDP endpoint for up to 15 seconds.
    """
    cdp_port = port or 9222
    kill_first = kill_existing is not False
    system = platform.system().lower()

    home = Path(os.environ.get("HOME", str(Path.home())))
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")

    candidates_by_platform: dict[str, list[str]] = {
        "darwin": [
            "/Applications/TradingView.app/Contents/MacOS/TradingView",
            str(home / "Applications/TradingView.app/Contents/MacOS/TradingView"),
        ],
        "windows": [
            f"{local_appdata}\\TradingView\\TradingView.exe",
            f"{program_files}\\TradingView\\TradingView.exe",
            f"{program_files_x86}\\TradingView\\TradingView.exe",
        ],
        "linux": [
            "/opt/TradingView/tradingview",
            "/opt/TradingView/TradingView",
            str(home / ".local/share/TradingView/TradingView"),
            "/usr/bin/tradingview",
            "/snap/tradingview/current/tradingview",
        ],
    }
    candidates = candidates_by_platform.get(system, candidates_by_platform["linux"])

    tv_path: str | None = next((p for p in candidates if p and Path(p).exists()), None)

    if tv_path is None:
        # Fall back to PATH-based discovery; ``shutil.which`` is the modern
        # cross-platform replacement for the JS ``where``/``which`` shell-out.
        which_name = "TradingView.exe" if system == "windows" else "tradingview"
        located = shutil.which(which_name)
        if located and Path(located).exists():
            tv_path = located

    if tv_path is None and system == "darwin":
        # macOS Spotlight knows about apps installed outside the standard
        # locations; this matches the JS fallback exactly.
        try:
            found = subprocess.check_output(
                ["mdfind", "kMDItemFSName == TradingView.app"],
                timeout=5,
                text=True,
            ).strip().splitlines()
            if found:
                candidate = f"{found[0]}/Contents/MacOS/TradingView"
                if Path(candidate).exists():
                    tv_path = candidate
        except (subprocess.SubprocessError, OSError):
            pass

    if tv_path is None:
        searched = ", ".join(candidates)
        raise RuntimeError(
            f"TradingView not found on {system}. Searched: {searched}. "
            f"Launch manually with: /path/to/TradingView --remote-debugging-port={cdp_port}"
        )

    if kill_first:
        try:
            if system == "windows":
                subprocess.run(
                    ["taskkill", "/F", "/IM", "TradingView.exe"],
                    timeout=5,
                    check=False,
                )
            else:
                subprocess.run(["pkill", "-f", "TradingView"], timeout=5, check=False)
            await asyncio.sleep(1.5)
        except (subprocess.SubprocessError, OSError):
            # The process may legitimately not be running yet — ignore.
            pass

    child = subprocess.Popen(  # noqa: S603 — controlled binary path, controlled args
        [tv_path, f"--remote-debugging-port={cdp_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(15):
        await asyncio.sleep(1.0)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"http://localhost:{cdp_port}/json/version")
                resp.raise_for_status()
                info = resp.json()
            return {
                "success": True,
                "platform": system,
                "binary": tv_path,
                "pid": child.pid,
                "cdp_port": cdp_port,
                "cdp_url": f"http://localhost:{cdp_port}",
                "browser": info.get("Browser"),
                "user_agent": info.get("User-Agent"),
            }
        except httpx.HTTPError:
            continue
        except json.JSONDecodeError:
            continue

    return {
        "success": True,
        "platform": system,
        "binary": tv_path,
        "pid": child.pid,
        "cdp_port": cdp_port,
        "cdp_ready": False,
        "warning": (
            "TradingView launched but CDP not responding yet. It may still be "
            "loading. Try tv_health_check in a few seconds."
        ),
    }
