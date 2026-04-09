"""Core Pine Script logic: editor control, compile, errors, console, static analysis.

All functions that touch the Pine Editor first call :func:`ensure_pine_editor_open`
which activates the bottom panel, waits for the Monaco editor to hydrate its
React fiber, and returns a handle to the live ``IStandaloneCodeEditor``
instance. The IIFE that locates Monaco walks the React fiber tree because
TradingView does not expose the editor through any public API.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import anyio
import httpx

from ..connection import evaluate, get_client

# Injected into the page to find the Monaco editor within TradingView's React fiber tree.
FIND_MONACO: str = """
  (function findMonacoEditor() {
    var container = document.querySelector('.monaco-editor.pine-editor-monaco');
    if (!container) return null;
    var el = container;
    var fiberKey;
    for (var i = 0; i < 20; i++) {
      if (!el) break;
      fiberKey = Object.keys(el).find(function(k) { return k.startsWith('__reactFiber$'); });
      if (fiberKey) break;
      el = el.parentElement;
    }
    if (!fiberKey) return null;
    var current = el[fiberKey];
    for (var d = 0; d < 15; d++) {
      if (!current) break;
      if (current.memoizedProps && current.memoizedProps.value && current.memoizedProps.value.monacoEnv) {
        var env = current.memoizedProps.value.monacoEnv;
        if (env.editor && typeof env.editor.getEditors === 'function') {
          var editors = env.editor.getEditors();
          if (editors.length > 0) return { editor: editors[0], env: env };
        }
      }
      current = current.return;
    }
    return null;
  })()
"""


async def ensure_pine_editor_open() -> bool:
    """Activate the Pine Editor panel and wait for Monaco to be ready."""
    already = await evaluate(f"(function() {{ var m = {FIND_MONACO}; return m !== null; }})()")
    if already:
        return True

    # Try the internal bottom-widget-bar API
    await evaluate("""
        (function() {
          var bwb = window.TradingView && window.TradingView.bottomWidgetBar;
          if (!bwb) return;
          if (typeof bwb.activateScriptEditorTab === 'function') bwb.activateScriptEditorTab();
          else if (typeof bwb.showWidget === 'function') bwb.showWidget('pine-editor');
        })()
    """)
    # Fall back to clicking the button
    await evaluate("""
        (function() {
          var btn = document.querySelector('[aria-label="Pine"]')
            || document.querySelector('[data-name="pine-dialog-button"]');
          if (btn) btn.click();
        })()
    """)

    for _ in range(50):
        await asyncio.sleep(0.2)
        ready = await evaluate(f"(function() {{ return {FIND_MONACO} !== null; }})()")
        if ready:
            return True
    return False


# ── Pure / offline functions ──────────────────────────────────────────────────


def analyze(*, source: str) -> dict[str, Any]:
    """Run static analysis on Pine Script code without compiling."""
    lines = source.split("\n")
    diagnostics: list[dict[str, Any]] = []

    # Detect version
    is_v6 = False
    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("//@version=6"):
            is_v6 = True
            break
        if trimmed.startswith("//@version="):
            break
        if trimmed == "" or trimmed.startswith("//"):
            continue
        break

    # Track array declarations
    arrays: dict[str, dict[str, Any]] = {}
    for i, line in enumerate(lines):
        m = re.search(r"(\w+)\s*=\s*array\.from\(([^)]*)\)", line)
        if m:
            args = m.group(2).strip()
            size = 0 if args == "" else len(args.split(","))
            arrays[m.group(1).strip()] = {"name": m.group(1).strip(), "size": size, "line": i + 1}
            continue
        m = re.search(r"(\w+)\s*=\s*array\.new(?:<\w+>|_\w+)\((\d+)?", line)
        if m:
            size = int(m.group(2)) if m.group(2) is not None else None
            arrays[m.group(1).strip()] = {"name": m.group(1).strip(), "size": size, "line": i + 1}

    # Check for out-of-bounds array access
    for i, line in enumerate(lines):
        for m in re.finditer(r"array\.(get|set)\(\s*(\w+)\s*,\s*(-?\d+)", line):
            method, arr_name, idx_str = m.group(1), m.group(2), m.group(3)
            idx = int(idx_str)
            info = arrays.get(arr_name)
            if not info or info["size"] is None:
                continue
            if idx < 0 or idx >= info["size"]:
                diagnostics.append({
                    "line": i + 1, "column": m.start() + 1,
                    "message": f"array.{method}({arr_name}, {idx}) — index {idx} out of bounds (array size is {info['size']})",
                    "severity": "error",
                })

    # Check for .first()/.last() on empty arrays
    for i, line in enumerate(lines):
        for m in re.finditer(r"(\w+)\.(first|last)\(\)", line):
            arr_name = m.group(1)
            if arr_name == "array":
                continue
            info = arrays.get(arr_name)
            if info and info["size"] == 0:
                diagnostics.append({
                    "line": i + 1, "column": m.start() + 1,
                    "message": f"{arr_name}.{m.group(2)}() called on possibly empty array (declared with size 0)",
                    "severity": "warning",
                })

    # Check for strategy functions without strategy() declaration
    has_strategy_decl = any(ln.strip().startswith("strategy(") for ln in lines)
    for i, line in enumerate(lines):
        if "strategy.entry" in line.strip() or "strategy.close" in line.strip():
            if not has_strategy_decl:
                diagnostics.append({
                    "line": i + 1, "column": 1,
                    "message": "strategy.entry/close used but no strategy() declaration found",
                    "severity": "error",
                })
            break

    # Old version suggestion
    if not is_v6 and "//@version=" in source:
        v_match = re.search(r"//@version=(\d+)", source)
        if v_match and int(v_match.group(1)) < 5:
            diagnostics.append({
                "line": 1, "column": 1,
                "message": f"Script uses Pine v{v_match.group(1)} — consider upgrading to v6",
                "severity": "info",
            })

    return {
        "success": True,
        "issue_count": len(diagnostics),
        "diagnostics": diagnostics,
        **({"note": "No static analysis issues found. Use pine_compile or pine_smart_compile for full server-side compilation check."} if not diagnostics else {}),
    }


async def check(*, source: str) -> dict[str, Any]:
    """Compile Pine Script via TradingView's server API (no chart needed)."""
    url = "https://pine-facade.tradingview.com/pine-facade/translate_light?user_name=Guest&pine_id=00000000-0000-0000-0000-000000000000"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.tradingview.com/",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data={"source": source}, headers=headers)
        resp.raise_for_status()
        result = resp.json()

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    inner = result.get("result")
    if inner:
        for e in inner.get("errors2", []):
            errors.append({"line": (e.get("start") or {}).get("line"), "column": (e.get("start") or {}).get("column"), "message": e.get("message")})
        for w in inner.get("warnings2", []):
            warnings.append({"line": (w.get("start") or {}).get("line"), "column": (w.get("start") or {}).get("column"), "message": w.get("message")})
    if result.get("error") and isinstance(result["error"], str):
        errors.append({"message": result["error"]})

    compiled = len(errors) == 0
    return {
        "success": True,
        "compiled": compiled,
        "error_count": len(errors),
        "warning_count": len(warnings),
        **({"errors": errors} if errors else {}),
        **({"warnings": warnings} if warnings else {}),
        **({"note": "Pine Script compiled successfully."} if compiled else {}),
    }


# ── Functions requiring TradingView connection ────────────────────────────────


async def get_source() -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor or Monaco not found.")
    source = await evaluate(f"(function() {{ var m = {FIND_MONACO}; if (!m) return null; return m.editor.getValue(); }})()")
    if source is None:
        raise RuntimeError("Monaco editor found but getValue() returned null.")
    return {"success": True, "source": source, "line_count": source.count("\n") + 1, "char_count": len(source)}


async def set_source(*, source: str) -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")
    escaped = json.dumps(source)
    ok = await evaluate(f"(function() {{ var m = {FIND_MONACO}; if (!m) return false; m.editor.setValue({escaped}); return true; }})()")
    if not ok:
        raise RuntimeError("Monaco found but setValue() failed.")
    return {"success": True, "lines_set": source.count("\n") + 1}


async def compile_script() -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")
    clicked = await evaluate("""
        (function() {
          var btns = document.querySelectorAll('button');
          var fallback = null; var saveBtn = null;
          for (var i = 0; i < btns.length; i++) {
            var text = btns[i].textContent.trim();
            if (/save and add to chart/i.test(text)) { btns[i].click(); return 'Save and add to chart'; }
            if (!fallback && /^(Add to chart|Update on chart)/i.test(text)) fallback = btns[i];
            if (!saveBtn && btns[i].className.indexOf('saveButton') !== -1 && btns[i].offsetParent !== null) saveBtn = btns[i];
          }
          if (fallback) { fallback.click(); return fallback.textContent.trim(); }
          if (saveBtn) { saveBtn.click(); return 'Pine Save'; }
          return null;
        })()
    """)
    if not clicked:
        tab = await get_client()
        def _key():
            tab.Input.dispatchKeyEvent(type="keyDown", modifiers=2, key="Enter", code="Enter", windowsVirtualKeyCode=13)
            tab.Input.dispatchKeyEvent(type="keyUp", key="Enter", code="Enter")
        await anyio.to_thread.run_sync(_key)
    await asyncio.sleep(2.0)
    return {"success": True, "button_clicked": clicked or "keyboard_shortcut", "source": "dom_fallback"}


async def smart_compile() -> dict[str, Any]:
    """Compile, check for errors, and report study changes — the all-in-one workflow."""
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")

    studies_before = await evaluate("""
        (function() {
          try { var chart = window.TradingViewApi._activeChartWidgetWV.value();
            if (chart && typeof chart.getAllStudies === 'function') return chart.getAllStudies().length;
          } catch(e) {} return null;
        })()
    """)
    compile_result = await compile_script()
    await asyncio.sleep(2.0)
    errors = await get_errors()
    studies_after = await evaluate("""
        (function() {
          try { var chart = window.TradingViewApi._activeChartWidgetWV.value();
            if (chart && typeof chart.getAllStudies === 'function') return chart.getAllStudies().length;
          } catch(e) {} return null;
        })()
    """)
    return {
        "success": True,
        "button_clicked": compile_result.get("button_clicked"),
        "has_errors": errors.get("has_errors", False),
        "error_count": errors.get("error_count", 0),
        "errors": errors.get("errors", []),
        "studies_before": studies_before,
        "studies_after": studies_after,
    }


async def get_errors() -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")
    errors = await evaluate(f"""
        (function() {{
          var m = {FIND_MONACO};
          if (!m) return [];
          var model = m.editor.getModel();
          if (!model) return [];
          var markers = m.env.editor.getModelMarkers({{ resource: model.uri }});
          return markers.map(function(mk) {{
            return {{ line: mk.startLineNumber, column: mk.startColumn, message: mk.message, severity: mk.severity }};
          }});
        }})()
    """) or []
    return {"success": True, "has_errors": len(errors) > 0, "error_count": len(errors), "errors": errors}


async def save_script() -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")
    tab = await get_client()
    def _save():
        tab.Input.dispatchKeyEvent(type="keyDown", modifiers=2, key="s", code="KeyS", windowsVirtualKeyCode=83)
        tab.Input.dispatchKeyEvent(type="keyUp", key="s", code="KeyS")
    await anyio.to_thread.run_sync(_save)
    await asyncio.sleep(0.8)
    dialog_handled = await evaluate("""
        (function() {
          var btns = document.querySelectorAll('button');
          for (var i = 0; i < btns.length; i++) {
            var text = btns[i].textContent.trim();
            if (text === 'Save' && btns[i].offsetParent !== null) {
              var parent = btns[i].closest('[class*="dialog"], [class*="modal"], [role="dialog"]');
              if (parent) { btns[i].click(); return true; }
            }
          }
          return false;
        })()
    """)
    if dialog_handled:
        await asyncio.sleep(0.5)
    return {"success": True, "action": "saved_with_dialog" if dialog_handled else "Ctrl+S_dispatched"}


async def get_console() -> dict[str, Any]:
    if not await ensure_pine_editor_open():
        raise RuntimeError("Could not open Pine Editor.")
    entries = await evaluate("""
        (function() {
          var results = [];
          var rows = document.querySelectorAll('[class*="consoleRow"], [class*="log-"], [class*="consoleLine"]');
          if (rows.length === 0) {
            var bottomArea = document.querySelector('[class*="layout__area--bottom"]');
            if (bottomArea) rows = bottomArea.querySelectorAll('[class*="message"], [class*="log"], [class*="console"]');
          }
          for (var i = 0; i < rows.length; i++) {
            var text = rows[i].textContent.trim();
            if (!text) continue;
            var ts = null;
            var tsMatch = text.match(/^(\\d{4}-\\d{2}-\\d{2}\\s+)?\\d{2}:\\d{2}:\\d{2}/);
            if (tsMatch) ts = tsMatch[0];
            var type = 'info';
            var cls = rows[i].className || '';
            if (/error/i.test(cls) || /error/i.test(text.substring(0, 30))) type = 'error';
            else if (/compil/i.test(text.substring(0, 40))) type = 'compile';
            else if (/warn/i.test(cls)) type = 'warning';
            results.push({ timestamp: ts, type: type, message: text });
          }
          return results;
        })()
    """) or []
    return {"success": True, "entries": entries, "entry_count": len(entries)}
