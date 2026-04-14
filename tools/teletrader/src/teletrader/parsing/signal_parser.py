"""Regex-based parser for Telegram trading signal messages.

Supports formats like:
    XAUUSD Buy Trigger only Above 4756 📈
    SL 4736
    Target 4760 4764 4785+ 🎯

    GOLD Sell Below 2345
    SL: 2360
    TP1: 2340 TP2: 2330 TP3: 2310
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from teletrader.models.trading_signal import TradingSignal

# Known forex / commodity symbols (extendable)
KNOWN_SYMBOLS: set[str] = {
    "XAUUSD", "XAGUSD", "GOLD", "SILVER",
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    "GBPJPY", "EURJPY", "EURGBP", "AUDJPY", "CADJPY", "CHFJPY",
    "EURCHF", "EURAUD", "EURNZD", "GBPAUD", "GBPNZD", "GBPCAD", "GBPCHF",
    "AUDNZD", "AUDCAD", "AUDCHF", "NZDCAD", "NZDCHF", "CADCHF",
    "US30", "NAS100", "SPX500", "US500", "USTEC", "DJ30",
    "BTCUSD", "ETHUSD", "BTCUSDT", "ETHUSDT",
    "USOIL", "UKOIL", "WTI", "BRENT",
}

# Symbol aliases → canonical MT5 symbol
SYMBOL_ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "WTI": "USOIL",
    "BRENT": "UKOIL",
    "DJ30": "US30",
    "SPX500": "US500",
    "USTEC": "NAS100",
}

# Strip emoji and non-ASCII decorations
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FEFF"
    r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0"
    r"\U0000200D\U0000FE0F]+",
    flags=re.UNICODE,
)

# Direction keywords
_BUY_RE = re.compile(r"\b(buy|long)\b", re.IGNORECASE)
_SELL_RE = re.compile(r"\b(sell|short)\b", re.IGNORECASE)

# Entry trigger: "above 4756", "below 2345", "@ 4756", "at 4756"
_TRIGGER_RE = re.compile(
    r"(?:\b(?:above|below|at)\b|@)\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)

# Stop loss: "SL 4736", "SL: 4736", "Stop Loss 4736", "Stop Loss: 4736", "Stoploss 4736"
_SL_RE = re.compile(
    r"\b(?:sl|stop\s*loss)\s*:?\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)

# Take profit targets — multiple formats:
#   "Target 4760 4764 4785+"
#   "TP1: 4760 TP2: 4764 TP3: 4785"
#   "Targets: 4760/4764/4785"
_TARGET_HEADER_RE = re.compile(
    r"\b(?:target|targets|tp)\s*:?\s*", re.IGNORECASE
)
_TP_LABELED_RE = re.compile(
    r"\btp\s*\d?\s*:?\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")

# Lot size: "Lot 0.05", "Lots: 0.1", "lot size 0.05", "0.05 lots"
_LOT_RE = re.compile(
    r"\b(?:lot(?:s|[\s_-]*size)?)\s*:?\s*(\d+(?:\.\d+)?)"
    r"|(\d+(?:\.\d+)?)\s*lots?\b",
    re.IGNORECASE,
)

# Above / below keyword extraction
_ABOVE_RE = re.compile(r"\babove\b", re.IGNORECASE)
_BELOW_RE = re.compile(r"\bbelow\b", re.IGNORECASE)


def parse_signal(raw_text: str) -> TradingSignal | None:
    """Parse a Telegram trading signal message into a TradingSignal.

    Returns None if the message cannot be parsed as a valid signal.
    """
    if not raw_text or not raw_text.strip():
        return None

    # Clean emoji
    text = _EMOJI_RE.sub(" ", raw_text).strip()

    # --- Extract symbol ---
    symbol = _extract_symbol(text)
    if not symbol:
        return None

    # --- Extract direction ---
    direction = _extract_direction(text)
    if not direction:
        return None

    # --- Extract entry price ---
    trigger_match = _TRIGGER_RE.search(text)
    if not trigger_match:
        return None
    entry_price = float(trigger_match.group(1))

    # --- Determine order type ---
    order_type = _derive_order_type(direction, text)

    # --- Extract stop loss ---
    sl_match = _SL_RE.search(text)
    if not sl_match:
        return None
    stop_loss = float(sl_match.group(1))

    # --- Extract take profits ---
    take_profits = _extract_take_profits(text)
    if not take_profits:
        return None

    # --- Extract lot size (optional) ---
    lot_size = _extract_lot_size(text)

    # Resolve symbol alias
    canonical = SYMBOL_ALIASES.get(symbol.upper(), symbol.upper())

    return TradingSignal(
        signal_id=uuid.uuid4().hex,
        symbol=canonical,
        direction=direction,
        order_type=order_type,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profits=take_profits,
        lot_size=lot_size,
        raw_text=raw_text,
        parsed_at_utc=datetime.now(UTC),
    )


def _extract_symbol(text: str) -> str | None:
    """Extract trading symbol from the first word of the message."""
    words = text.split()
    if not words:
        return None

    candidate = words[0].upper().strip(".,;:!?")
    if candidate in KNOWN_SYMBOLS:
        return candidate

    # Try first two words combined (e.g. "XAU USD")
    if len(words) >= 2:
        combined = (words[0] + words[1]).upper().strip(".,;:!?")
        if combined in KNOWN_SYMBOLS:
            return combined

    return None


def _extract_direction(text: str) -> str | None:
    """Extract buy/sell direction."""
    has_buy = _BUY_RE.search(text)
    has_sell = _SELL_RE.search(text)

    if has_buy and not has_sell:
        return "buy"
    if has_sell and not has_buy:
        return "sell"
    if has_buy and has_sell:
        # Use the one that appears first
        return "buy" if has_buy.start() < has_sell.start() else "sell"
    return None


def _derive_order_type(
    direction: str, text: str
) -> str:
    """Derive pending order type from direction + above/below keyword.

    Buy + Above  = buy_stop   (price rises to entry)
    Buy + Below  = buy_limit  (price dips to entry)
    Sell + Above = sell_limit  (price rises to entry)
    Sell + Below = sell_stop   (price falls to entry)
    """
    has_above = bool(_ABOVE_RE.search(text))
    has_below = bool(_BELOW_RE.search(text))

    if direction == "buy":
        return "buy_limit" if has_below else "buy_stop"
    else:  # sell
        return "sell_limit" if has_above else "sell_stop"


def _extract_lot_size(text: str) -> float | None:
    """Extract lot size from the message, if present.

    Handles: "Lot 0.05", "Lots: 0.1", "lot size 0.05", "0.05 lots"
    """
    match = _LOT_RE.search(text)
    if not match:
        return None
    # Group 1 = "Lot 0.05" form, Group 2 = "0.05 lots" form
    value = match.group(1) or match.group(2)
    if value:
        lot = float(value)
        if lot > 0:
            return lot
    return None


def _extract_take_profits(text: str) -> list[float]:
    """Extract take-profit levels from the message.

    Handles:
      - "Target 4760 4764 4785+"
      - "TP1: 4760 TP2: 4764 TP3: 4785"
      - "Targets: 4760/4764/4785"
    """
    # First try labeled TP format: TP1: 4760, TP2: 4764
    labeled = _TP_LABELED_RE.findall(text)
    if len(labeled) >= 2:
        return [float(v) for v in labeled]

    # Find lines with "target" keyword
    lines = text.split("\n")
    for line in lines:
        if _TARGET_HEADER_RE.search(line):
            # Extract all numbers from the target line
            # Replace separators (/, |, ,) with spaces
            cleaned = re.sub(r"[/|,]", " ", line)
            # Remove the "target" keyword itself and any TP labels
            cleaned = _TARGET_HEADER_RE.sub("", cleaned)
            cleaned = re.sub(r"\btp\s*\d?\s*:?\s*", "", cleaned, flags=re.IGNORECASE)
            # Strip trailing + signs
            cleaned = cleaned.replace("+", " ")
            numbers = _NUMBER_RE.findall(cleaned)
            if numbers:
                return [float(n) for n in numbers]

    return []
