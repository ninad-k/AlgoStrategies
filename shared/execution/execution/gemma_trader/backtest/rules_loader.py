"""
backtest/rules_loader.py — load strategy_rules.yaml and merge per-symbol
filter/threshold overrides into the live trader's in-memory config.

Precedence: rules file > config.yaml. Unknown symbols fall back to config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "strategy_rules.yaml"


def load(rules_path: Path = DEFAULT_RULES_PATH) -> dict:
    """Load rules yaml. Returns empty dict if missing or malformed."""
    if not rules_path.exists():
        return {}
    try:
        with open(rules_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}


def save(rules: dict, rules_path: Path = DEFAULT_RULES_PATH) -> None:
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(rules, f, sort_keys=False)


def merge(config: dict, rules_path: Path = DEFAULT_RULES_PATH) -> dict:
    """
    Merge rules into config in-place under config['strategy_rules'].
    Does NOT overwrite config.yaml; the merged rules are attached at runtime
    so the live trader can consult them per-symbol via get_for_symbol().
    """
    rules = load(rules_path)
    config["strategy_rules"] = rules
    return rules


def get_for_symbol(config: dict, symbol: str) -> dict:
    """
    Return the resolved {filters, thresholds} block for a symbol. Empty dict
    if no rules are loaded or the symbol is not covered.
    """
    rules = config.get("strategy_rules") or {}
    symbols = rules.get("symbols") or {}
    block = symbols.get(symbol) or {}
    return {
        "filters": dict(block.get("filters") or {}),
        "thresholds": dict(block.get("thresholds") or {}),
    }


def bump_version(rules: dict) -> int:
    v = int(rules.get("version", 0)) + 1
    rules["version"] = v
    return v


def apply_proposal(rules: dict, symbol: str, path: str, new_value: Any) -> bool:
    """
    Apply a single validated proposal to the in-memory rules dict.
    Returns True if applied, False if path is invalid.
    path format: "filters.min_adx" or "thresholds.rsi_overbought".
    """
    parts = path.split(".", 1)
    if len(parts) != 2:
        return False
    section, key = parts
    if section not in ("filters", "thresholds"):
        return False
    sym_block = rules.setdefault("symbols", {}).setdefault(symbol, {})
    sec_block = sym_block.setdefault(section, {})
    sec_block[key] = new_value
    return True


def update_baseline(rules: dict, symbol: str, metrics: dict) -> None:
    sym_block = rules.setdefault("symbols", {}).setdefault(symbol, {})
    sym_block["baseline"] = {
        "expectancy_r": metrics.get("expectancy_r"),
        "max_dd_r": metrics.get("max_dd_r"),
        "trades": metrics.get("trades"),
        "win_rate": metrics.get("win_rate"),
    }
