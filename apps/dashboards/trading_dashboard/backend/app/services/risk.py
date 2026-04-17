import json
import os
from typing import Optional

_pip_sizes: dict = {}


def _load_pip_sizes():
    global _pip_sizes
    config_path = os.path.join(os.path.dirname(__file__), "../../config/pip_sizes.json")
    config_path = os.path.normpath(config_path)
    if os.path.exists(config_path):
        with open(config_path) as f:
            _pip_sizes = json.load(f)


_load_pip_sizes()


def get_pip_size(symbol: str) -> float:
    return _pip_sizes.get(symbol, _pip_sizes.get("default", 0.0001))


def compute_risk_metrics(trade: dict) -> dict:
    symbol = trade["symbol"]
    trade_type = trade["type"]
    open_price = trade.get("open_price") or 0
    close_price = trade.get("close_price")
    sl = trade.get("sl")
    tp = trade.get("tp")
    profit = float(trade.get("profit") or 0)
    lots = float(trade.get("lots") or 1)

    has_sl = sl is not None
    has_tp = tp is not None

    pip_size = get_pip_size(symbol)
    risk_pips: Optional[float] = None
    reward_pips: Optional[float] = None
    planned_rr: Optional[float] = None
    realised_rr: Optional[float] = None
    rr_deviation: Optional[float] = None

    if has_sl:
        risk_pips = abs(open_price - sl) / pip_size
        if risk_pips == 0:
            risk_pips = None

    if has_tp and risk_pips:
        reward_pips = abs(tp - open_price) / pip_size
        planned_rr = round(reward_pips / risk_pips, 4) if reward_pips else None

    if risk_pips and close_price:
        profit_pips = abs(close_price - open_price) / pip_size
        # direction: positive profit = win
        if trade_type == "BUY":
            signed = close_price - open_price
        else:
            signed = open_price - close_price
        realised_rr = round((signed / pip_size) / risk_pips, 4)

    if planned_rr is not None and realised_rr is not None:
        rr_deviation = round(realised_rr - planned_rr, 4)

    return {
        "has_sl": has_sl,
        "has_tp": has_tp,
        "risk_pips": round(risk_pips, 4) if risk_pips else None,
        "reward_pips": round(reward_pips, 4) if reward_pips else None,
        "planned_rr": planned_rr,
        "realised_rr": realised_rr,
        "rr_deviation": rr_deviation,
    }
