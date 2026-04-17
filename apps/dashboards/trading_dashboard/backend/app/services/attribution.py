from dataclasses import dataclass
from typing import Optional


@dataclass
class AttributionResult:
    category_type: str   # 'trader' | 'strategy'
    category_id: int
    attribution_level: int
    confidence: float = 1.0


def attribute_trade(
    trade: dict,
    traders: list[dict],
    strategies: list[dict],
) -> list[AttributionResult]:
    """
    Walk L1-L6 cascade for a single trade.
    Returns list of AttributionResult — may be empty (guest), or have 1-2 entries
    (e.g., one trader + one strategy matched independently).
    """
    results: list[AttributionResult] = []
    magic = trade.get("magic")
    comment = (trade.get("comment") or "").lower()
    lots = float(trade.get("lots") or 0)
    symbol = (trade.get("symbol") or "").upper()
    account_id = trade.get("account_id")

    # ── L1: Magic number → strategy ──────────────────────────────────────────
    if magic:
        matches = [s for s in strategies if s.get("magic_number") == magic]
        if len(matches) == 1:
            results.append(AttributionResult("strategy", matches[0]["id"], 1))
        elif len(matches) > 1:
            return []  # conflict → guest

    # ── L2: Comment prefix → strategy ────────────────────────────────────────
    if not _has_strategy(results):
        for strat in strategies:
            prefix = (strat.get("comment_prefix") or "").lower()
            if prefix and comment.startswith(prefix):
                results.append(AttributionResult("strategy", strat["id"], 2))
                break

    # ── L3: Lot size → trader ─────────────────────────────────────────────────
    if not _has_trader(results):
        trader_lot_matches = [
            t for t in traders
            if t.get("default_lot_size") is not None
            and abs(float(t["default_lot_size"]) - lots) < 0.001
            and t["id"] != 0   # exclude Guest/Common
        ]
        if len(trader_lot_matches) == 1:
            results.append(AttributionResult("trader", trader_lot_matches[0]["id"], 3))
        elif len(trader_lot_matches) > 1:
            pass  # conflict at L3 — fall through to L4+

    # ── L4: Lot size → strategy ───────────────────────────────────────────────
    if not _has_strategy(results):
        strat_lot_matches = [
            s for s in strategies
            if s.get("lot_size") is not None
            and abs(float(s["lot_size"]) - lots) < 0.001
        ]
        if len(strat_lot_matches) == 1:
            results.append(AttributionResult("strategy", strat_lot_matches[0]["id"], 4))

    # ── L5: Symbol list → strategy ────────────────────────────────────────────
    if not _has_strategy(results):
        for strat in strategies:
            sym_filter = [s.upper() for s in (strat.get("symbol_filter") or [])]
            if sym_filter and symbol in sym_filter:
                results.append(AttributionResult("strategy", strat["id"], 5))
                break

    # ── L6: Account owner → trader ────────────────────────────────────────────
    if not _has_trader(results):
        for trader in traders:
            linked_accounts = trader.get("linked_accounts") or []
            if account_id in linked_accounts and trader["id"] != 0:
                results.append(AttributionResult("trader", trader["id"], 6))
                break

    return results


def _has_trader(results: list[AttributionResult]) -> bool:
    return any(r.category_type == "trader" for r in results)


def _has_strategy(results: list[AttributionResult]) -> bool:
    return any(r.category_type == "strategy" for r in results)
