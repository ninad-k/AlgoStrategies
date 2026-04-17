"""Parse raw webhook body into a structured trade alert.

Supported formats
-----------------
**CSV (recommended for TradingView):**
    strategy,action,symbol[,key=value,...]

Examples:
    ema200,buy,EURUSD
    ema200,sell,XAUUSD,sl=2010.50,tp1=1990.00,tp2=1980.00,tp3=1970.00
    smartmoney,buy,GBPUSD,lots=0.20,sl=1.2600,tp1=1.2700,tp2=1.2800,trailing=1.2750:0.0020

**JSON:**
    {"strategy":"ema200","action":"buy","symbol":"EURUSD","sl":1.0800,...}

Key-value parameters
--------------------
sl          Stop loss price
tp1         Take profit level 1 price
tp2         Take profit level 2 price
tp3         Take profit level 3 price
lots        Override lot size
close1      % of position to close at tp1 (default from connection config)
close2      % of position to close at tp2
close3      % of position to close at tp3
trailing    activation_price:trailing_distance  (colon-separated)
magic       EA magic number
comment     Trade comment
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class PartialTP:
    level: int
    price: float
    close_percent: float | None = None


@dataclass
class TrailingConfig:
    activation_price: float
    trailing_distance: float


@dataclass
class ParsedAlert:
    strategy: str
    action: str  # "buy" or "sell"
    symbol: str
    lots: float | None = None
    stop_loss: float | None = None
    partial_tps: list[PartialTP] = field(default_factory=list)
    trailing: TrailingConfig | None = None
    magic: int = 0
    comment: str = ""


class AlertParseError(Exception):
    """Raised when the raw alert body cannot be parsed."""


def parse_alert(raw_body: str) -> ParsedAlert:
    """Parse a raw webhook body into a ``ParsedAlert``.

    Raises ``AlertParseError`` on malformed input.
    """
    text = raw_body.strip()
    if not text:
        raise AlertParseError("Empty alert body")

    if text.startswith("{"):
        return _parse_json(text)
    if text.startswith("["):
        raise AlertParseError("JSON body must be an object, not an array")
    return _parse_csv(text)


def _parse_json(text: str) -> ParsedAlert:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AlertParseError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise AlertParseError("JSON body must be an object")

    strategy = data.get("strategy") or data.get("s")
    action = data.get("action") or data.get("a")
    symbol = data.get("symbol") or data.get("sym")

    if not strategy or not action or not symbol:
        raise AlertParseError(
            "JSON must contain 'strategy' (or 's'), 'action' (or 'a'), 'symbol' (or 'sym')"
        )

    action = action.lower()
    if action not in ("buy", "sell"):
        raise AlertParseError(f"Invalid action '{action}', must be 'buy' or 'sell'")

    alert = ParsedAlert(
        strategy=str(strategy),
        action=action,
        symbol=str(symbol).upper(),
    )

    if "lots" in data:
        alert.lots = float(data["lots"])
    if "sl" in data:
        alert.stop_loss = float(data["sl"])
    if "magic" in data:
        alert.magic = int(data["magic"])
    if "comment" in data:
        alert.comment = str(data["comment"])

    for i in range(1, 4):
        tp_key = f"tp{i}"
        close_key = f"close{i}"
        if tp_key in data:
            alert.partial_tps.append(
                PartialTP(
                    level=i,
                    price=float(data[tp_key]),
                    close_percent=float(data[close_key]) if close_key in data else None,
                )
            )

    if "trailing" in data:
        t = data["trailing"]
        if isinstance(t, dict):
            alert.trailing = TrailingConfig(
                activation_price=float(t["activation_price"]),
                trailing_distance=float(t["trailing_distance"]),
            )
        elif isinstance(t, str) and ":" in t:
            parts = t.split(":")
            alert.trailing = TrailingConfig(
                activation_price=float(parts[0]),
                trailing_distance=float(parts[1]),
            )

    return alert


def _parse_csv(text: str) -> ParsedAlert:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        raise AlertParseError(
            f"CSV alert needs at least 3 fields (strategy,action,symbol), got {len(parts)}"
        )

    strategy = parts[0]
    action = parts[1].lower()
    symbol = parts[2].upper()

    if action not in ("buy", "sell"):
        raise AlertParseError(f"Invalid action '{action}', must be 'buy' or 'sell'")

    if not strategy:
        raise AlertParseError("Strategy name cannot be empty")
    if not symbol:
        raise AlertParseError("Symbol cannot be empty")

    alert = ParsedAlert(strategy=strategy, action=action, symbol=symbol)

    for part in parts[3:]:
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip().lower()
        val = val.strip()

        if key == "sl":
            alert.stop_loss = float(val)
        elif key == "lots":
            alert.lots = float(val)
        elif key == "magic":
            alert.magic = int(val)
        elif key == "comment":
            alert.comment = val
        elif key in ("tp1", "tp2", "tp3"):
            level = int(key[2])
            alert.partial_tps.append(PartialTP(level=level, price=float(val)))
        elif key in ("close1", "close2", "close3"):
            level = int(key[5])
            existing = next((tp for tp in alert.partial_tps if tp.level == level), None)
            if existing:
                existing.close_percent = float(val)
            else:
                alert.partial_tps.append(
                    PartialTP(level=level, price=0.0, close_percent=float(val))
                )
        elif key == "trailing" and ":" in val:
            act_price, trail_dist = val.split(":")
            alert.trailing = TrailingConfig(
                activation_price=float(act_price),
                trailing_distance=float(trail_dist),
            )

    alert.partial_tps.sort(key=lambda tp: tp.level)

    return alert
