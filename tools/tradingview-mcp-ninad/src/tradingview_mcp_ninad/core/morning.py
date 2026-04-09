"""Morning brief workflow: scan watchlist, read indicators, return structured data.

The brief itself does not pass judgment — it collects chart state + indicator
values for every watchlist symbol and returns the raw data alongside the bias
criteria from ``rules.json``. The model calling the tool applies the criteria
and produces the final SYMBOL | BIAS | KEY LEVEL | WATCH lines.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..logging_config import state_dir
from ..rules.config import RulesConfig
from . import chart, data

SESSIONS_DIR = state_dir() / "sessions"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # tools/tradingview-mcp-ninad


def _load_rules(rules_path: str | None) -> tuple[RulesConfig, str]:
    """Search candidate paths and return the first parseable rules file."""
    home = Path.home()
    candidates: list[Path] = [
        *([] if not rules_path else [Path(rules_path)]),
        _PROJECT_ROOT / "rules.json",
        home / ".tradingview-mcp" / "rules.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                return RulesConfig.model_validate(raw), str(p)
            except Exception as exc:
                raise RuntimeError(f"Failed to parse rules.json at {p}: {exc}") from exc
    paths_str = "\n".join(f"  - {p}" for p in candidates)
    raise RuntimeError(
        "No rules.json found. Copy rules.example.json to rules.json and fill in your trading rules.\n"
        f"Looked in:\n{paths_str}"
    )


async def run_brief(*, rules_path: str | None = None) -> dict[str, Any]:
    """Execute the morning brief: iterate the watchlist, collect readings."""
    rules, loaded_from = _load_rules(rules_path)
    if not rules.watchlist:
        raise RuntimeError("rules.json watchlist is empty. Add at least one symbol.")

    # Snapshot current chart state so we can restore it after the scan
    original_symbol: str | None = None
    original_timeframe: str | None = None
    try:
        current = await chart.get_state()
        original_symbol = current.get("symbol")
        original_timeframe = current.get("resolution")
    except Exception:
        pass

    results: list[dict[str, Any]] = []
    for symbol in rules.watchlist:
        try:
            await chart.set_symbol(symbol=symbol)
            await asyncio.sleep(0.9)
            await chart.set_timeframe(timeframe=rules.default_timeframe)
            await asyncio.sleep(0.9)

            state, indicators, quote = await asyncio.gather(
                chart.get_state(),
                data.get_study_values(),
                data.get_quote(symbol=None),
            )
            results.append({
                "symbol": symbol,
                "timeframe": rules.default_timeframe,
                "state": state,
                "indicators": indicators,
                "quote": quote,
            })
        except Exception as exc:
            results.append({"symbol": symbol, "error": str(exc)})

    # Restore original chart
    if original_symbol:
        try:
            await chart.set_symbol(symbol=original_symbol)
            if original_timeframe:
                await chart.set_timeframe(timeframe=original_timeframe)
        except Exception:
            pass

    return {
        "success": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "rules_loaded_from": loaded_from,
        "rules": {
            "bias_criteria": rules.bias_criteria.model_dump() if rules.bias_criteria else None,
            "risk_rules": rules.risk_rules or None,
            "notes": rules.notes or None,
        },
        "symbols_scanned": results,
        "instruction": (
            "For each symbol in symbols_scanned, apply the bias_criteria from rules to the indicator readings. "
            "Output one line per symbol: SYMBOL | BIAS: [bullish/bearish/neutral] | KEY LEVEL: [price] | WATCH: [what to monitor]. "
            "End with a one-sentence overall market read. Be direct. No preamble."
        ),
    }


def save_session(*, brief: str, date: str | None = None) -> dict[str, Any]:
    """Persist today's brief text to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = date or datetime.now(UTC).strftime("%Y-%m-%d")
    file_path = SESSIONS_DIR / f"{date_str}.json"
    existing = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else {}
    record = {
        **existing,
        "date": date_str,
        "saved_at": datetime.now(UTC).isoformat(),
        "brief": brief,
    }
    file_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"success": True, "path": str(file_path), "date": date_str}


def get_session(*, date: str | None = None) -> dict[str, Any]:
    """Retrieve a saved session by date (defaults to today, then yesterday)."""
    date_str = date or datetime.now(UTC).strftime("%Y-%m-%d")
    file_path = SESSIONS_DIR / f"{date_str}.json"
    if file_path.exists():
        return {"success": True, **json.loads(file_path.read_text(encoding="utf-8"))}

    from datetime import timedelta
    yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_path = SESSIONS_DIR / f"{yesterday}.json"
    if yesterday_path.exists():
        return {
            "success": True,
            "note": "No session for today — returning yesterday",
            **json.loads(yesterday_path.read_text(encoding="utf-8")),
        }
    return {
        "success": False,
        "error": f"No session found for {date_str} or {yesterday}",
        "sessions_dir": str(SESSIONS_DIR),
    }
