"""Parse TradingView webhook alerts into WebhookAlert models.

Supports two formats:
1. JSON: {"action":"buy","symbol":"EURUSD","lot":0.1,"sl":20,"tp":40}
2. Plain text: token,buy,EURUSD,sl=20,tp=40,lot=0.1
"""

from __future__ import annotations

import json
import logging

from .models import PartialTPConfig, SignalAction, TrailingConfig, WebhookAlert

log = logging.getLogger(__name__)


def parse_alert(body: bytes, content_type: str) -> WebhookAlert:
    """Parse raw webhook body into a WebhookAlert."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("Empty alert body")

    if "json" in content_type.lower():
        return _parse_json(text)

    # Try JSON first even for non-json content types
    if text.startswith("{"):
        try:
            return _parse_json(text)
        except Exception:
            pass

    return _parse_text(text)


def _parse_json(text: str) -> WebhookAlert:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")

    # Normalize action to lowercase
    if "action" in data:
        data["action"] = str(data["action"]).lower().strip()

    # Parse partial TP shorthand: tp1=10@50%,tp2=20@30%,tp3=40@20%
    _extract_partial_tp_shorthand(data)
    _extract_trailing_shorthand(data)

    return WebhookAlert(**data)


def _parse_text(text: str) -> WebhookAlert:
    """Parse comma-separated plain text format.

    Format: token,action,symbol[,key=value...]
    Example: abc123,buy,XAUUSD,sl=50,tp=100,lot=0.1,risk=1
    """
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        raise ValueError(f"Text alert needs at least token,action,symbol. Got: {text}")

    token = parts[0]
    action = parts[1].lower()
    symbol = parts[2].upper()

    # Validate action
    try:
        SignalAction(action)
    except ValueError:
        raise ValueError(f"Unknown action: {action}")

    data: dict = {"token": token, "action": action, "symbol": symbol}

    # Parse remaining key=value pairs
    for part in parts[3:]:
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip().lower()
        val = val.strip()

        if key in ("lot", "sl", "tp", "sl_pips", "tp_pips", "price", "risk_percent"):
            data[key] = float(val)
        elif key in ("magic", "time_exit_minutes"):
            data[key] = int(val)
        elif key == "risk":
            data["risk_percent"] = float(val)
        elif key == "comment":
            data["comment"] = val

    _extract_partial_tp_shorthand(data)
    _extract_trailing_shorthand(data)

    return WebhookAlert(**data)


def _extract_partial_tp_shorthand(data: dict) -> None:
    """Extract TP1/TP2/TP3 shorthand into PartialTPConfig."""
    tp_fields = {}
    for i in range(1, 4):
        key = f"tp{i}"
        if key not in data:
            continue
        raw = str(data.pop(key))
        if "@" in raw:
            pips_str, pct_str = raw.split("@", 1)
            tp_fields[f"tp{i}_pips"] = float(pips_str)
            tp_fields[f"tp{i}_percent"] = float(pct_str.rstrip("%"))
        else:
            tp_fields[f"tp{i}_pips"] = float(raw)

    if tp_fields:
        existing = data.get("partial_tp") or {}
        if isinstance(existing, dict):
            existing.update(tp_fields)
        else:
            existing = tp_fields
        data["partial_tp"] = PartialTPConfig(**existing)


def _extract_trailing_shorthand(data: dict) -> None:
    """Extract trailing shorthand keys."""
    trail_fields = {}
    for key in ("trail_activation", "trail_distance", "trail_step"):
        if key in data:
            mapped = key.replace("trail_", "") + "_pips"
            trail_fields[mapped] = float(data.pop(key))
            trail_fields["enabled"] = True

    if trail_fields:
        existing = data.get("trailing") or {}
        if isinstance(existing, dict):
            existing.update(trail_fields)
        else:
            existing = trail_fields
        data["trailing"] = TrailingConfig(**existing)
