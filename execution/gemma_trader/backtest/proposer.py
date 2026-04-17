"""
backtest/proposer.py — ask Gemma for <=3 filter/threshold deltas per symbol
per run. Strict JSON schema, strict whitelist. Any off-schema output is
rejected and baseline is kept.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests


logger = logging.getLogger("backtest.proposer")


# Whitelist of editable paths with (min, max) numeric bounds.
EDITABLE_PATHS: dict[str, tuple[float, float]] = {
    "filters.min_adx":                (0.0,   60.0),
    "filters.min_vol_ratio":          (0.0,   5.0),
    "filters.block_when_bb_width_below": (0.0, 20.0),
    "thresholds.rsi_oversold":        (5.0,   45.0),
    "thresholds.rsi_overbought":      (55.0,  95.0),
    "thresholds.sl_atr":              (0.3,   3.0),
    "thresholds.tp_atr":              (0.5,   6.0),
    "thresholds.cooldown_min":        (0.0,   60.0),
    "thresholds.min_confidence":      (0.3,   0.95),
}


SYSTEM_PROMPT = (
    "You are a conservative trading-rule tuner. You will be given a symbol, its "
    "current rules, and the in-sample backtest result. Propose at most 3 small "
    "numeric tweaks to filters/thresholds that could improve expectancy without "
    "raising drawdown. Only numeric changes; no new keys, no logic changes. "
    "Respond with JSON only, no prose."
)


def _build_prompt(symbol: str, rules: dict, is_metrics: dict) -> str:
    return f"""Symbol: {symbol}

Current rules:
{json.dumps(rules, indent=2)}

In-sample metrics:
{json.dumps(is_metrics, indent=2)}

Editable paths (with numeric bounds):
{json.dumps({k: list(v) for k, v in EDITABLE_PATHS.items()}, indent=2)}

Respond with JSON in this exact shape:
{{
  "symbol": "{symbol}",
  "rationale": "one short sentence",
  "proposals": [
    {{"path": "filters.min_adx", "from": <old>, "to": <new>, "reason": "short"}}
  ]
}}
Max 3 proposals. If nothing should change, return "proposals": []."""


def _call_ollama(config: dict, prompt: str) -> str | None:
    ollama_cfg = config.get("ollama", {})
    url = ollama_cfg.get("url", "http://localhost:11434/api/generate")
    model = ollama_cfg.get("model", "gemma4")
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": float(ollama_cfg.get("temperature", 0.1)),
                    "num_predict": int(ollama_cfg.get("num_predict", 2048)),
                },
            },
            timeout=int(ollama_cfg.get("timeout", 180)),
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        return None


def _parse_json_block(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = [l for l in cleaned.split("\n") if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end])
    except json.JSONDecodeError:
        return None


def _validate_proposals(obj: dict, symbol: str) -> list[dict]:
    """Return list of validated proposals; invalid entries are dropped."""
    if not isinstance(obj, dict):
        return []
    if obj.get("symbol") != symbol:
        logger.warning(f"Proposer returned wrong symbol: {obj.get('symbol')!r}")
        return []
    proposals = obj.get("proposals")
    if not isinstance(proposals, list):
        return []
    valid: list[dict] = []
    for p in proposals[:3]:
        if not isinstance(p, dict):
            continue
        path = p.get("path")
        new_val = p.get("to")
        if not isinstance(path, str) or path not in EDITABLE_PATHS:
            logger.warning(f"Reject off-whitelist path: {path!r}")
            continue
        try:
            new_val_f = float(new_val)
        except (TypeError, ValueError):
            logger.warning(f"Reject non-numeric value for {path}: {new_val!r}")
            continue
        lo, hi = EDITABLE_PATHS[path]
        if not (lo <= new_val_f <= hi):
            logger.warning(f"Reject out-of-range value for {path}: {new_val_f} not in [{lo}, {hi}]")
            continue
        valid.append({
            "path": path,
            "from": p.get("from"),
            "to": new_val_f,
            "reason": str(p.get("reason", ""))[:200],
        })
    return valid


def propose(symbol: str, rules_block: dict, is_metrics: dict, config: dict) -> dict:
    """
    Single Gemma call. Returns:
        {"symbol": ..., "rationale": ..., "proposals": [validated...]}
    Proposals are already validated against the whitelist + bounds.
    """
    prompt = _build_prompt(symbol, rules_block, is_metrics)
    raw = _call_ollama(config, prompt)
    if raw is None:
        return {"symbol": symbol, "rationale": "ollama unavailable", "proposals": []}
    parsed = _parse_json_block(raw)
    if parsed is None:
        logger.warning(f"Could not parse JSON from proposer response for {symbol}")
        return {"symbol": symbol, "rationale": "parse error", "proposals": []}
    return {
        "symbol": symbol,
        "rationale": str(parsed.get("rationale", ""))[:500],
        "proposals": _validate_proposals(parsed, symbol),
    }
