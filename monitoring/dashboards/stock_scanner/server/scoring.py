"""
Composite scoring engine for all four stock categories.

Scores are 0-100.  Each function returns (score, breakdown_dict).
The breakdown dict has entries: { 'Criterion Name': {'pts': X, 'max': Y, 'val': Z} }
"""

from __future__ import annotations


# ── Red-flag detector ──────────────────────────────────────────────────────────

def check_red_flags(tech: dict, fund: dict) -> list[str]:
    flags: list[str] = []

    spf = fund.get("short_pct_float")
    if spf and spf > 25:
        flags.append(f"High short interest ({spf:.0f}%)")

    gm = fund.get("gross_margin")
    if gm is not None and gm < 0:
        flags.append("Negative gross margin")

    de = fund.get("debt_equity")
    if de is not None and de > 200:
        flags.append(f"Extreme leverage (D/E {de:.0f}%)")

    if fund.get("eps_trend") == "DECLINING":
        flags.append("Declining earnings")

    if fund.get("insider_buy_signal") == "SELLING":
        flags.append("Insider selling")

    if tech.get("stage") == 4:
        flags.append("Stage 4 downtrend")

    return flags


# ── 2-3 Day swing score ────────────────────────────────────────────────────────

def score_swing_short(tech: dict, fund: dict) -> tuple[float, dict]:
    """
    Looks for: RSI bounce zone, volume spike, near support, bullish candle, above EMA20.
    """
    bd: dict = {}
    total = 0.0

    # 1. RSI bounce zone (20 pts)
    rsi = tech.get("rsi", 50)
    if 25 <= rsi <= 40:
        pts = 20
    elif 40 < rsi <= 50:
        pts = 12
    elif rsi < 25:
        pts = 8   # extreme oversold — might keep falling
    else:
        pts = 0
    bd["RSI Bounce Zone"] = {"pts": pts, "max": 20, "val": rsi}
    total += pts

    # 2. Volume spike (20 pts)
    vr = tech.get("volume_ratio", 1.0)
    if vr >= 3.0:   pts = 20
    elif vr >= 2.0: pts = 15
    elif vr >= 1.5: pts = 8
    else:           pts = 0
    bd["Volume Spike"] = {"pts": pts, "max": 20, "val": round(vr, 1)}
    total += pts

    # 3. Near support (20 pts)
    if tech.get("near_support"):
        pts = 20
    else:
        pfl = tech.get("pct_from_low", 100)
        pts = 10 if pfl < 10 else (5 if pfl < 20 else 0)
    bd["Near Support"] = {"pts": pts, "max": 20, "val": tech.get("near_support", False)}
    total += pts

    # 4. Bullish candle (20 pts)
    if tech.get("bullish_candle"):
        pts = 20
    elif (tech.get("price_change_pct") or 0) > 0:
        pts = 8
    else:
        pts = 0
    bd["Bullish Candle"] = {"pts": pts, "max": 20, "val": tech.get("bullish_candle", False)}
    total += pts

    # 5. Above EMA20 (20 pts)
    price = tech.get("price", 0) or 0
    ema20 = tech.get("ema20", price) or price
    if price > ema20 > 0:         pts = 20
    elif price > ema20 * 0.98:    pts = 10
    else:                         pts = 0
    bd["Above EMA20"] = {"pts": pts, "max": 20, "val": price > ema20}
    total += pts

    # Overbought penalty
    if rsi > 70:
        total = max(0, total - 20)
        bd["Overbought Penalty"] = {"pts": -20, "max": 0, "val": rsi}

    return round(min(total, 100), 1), bd


# ── 2-3 Week positional swing score ───────────────────────────────────────────

def score_swing_medium(tech: dict, fund: dict) -> tuple[float, dict]:
    """
    Looks for: Stage 2, volume confirmation, near 52W high, RS vs SPY, VCP.
    """
    bd: dict = {}
    total = 0.0
    stage = tech.get("stage", 0)

    # Auto-zero for Stage 4
    if stage == 4:
        return 0.0, {"Stage 4 Penalty": {"pts": 0, "max": 100, "val": "Stage 4 downtrend"}}

    # 1. Stage 2 EMA alignment (25 pts)
    if stage == 2:   pts = 25
    elif stage == 1: pts = 10
    else:            pts = 0
    bd["Stage 2 (EMA Alignment)"] = {"pts": pts, "max": 25, "val": f"Stage {stage}"}
    total += pts

    # 2. Volume confirmation (20 pts)
    vr = tech.get("volume_ratio", 1.0)
    if vr >= 2.0:   pts = 20
    elif vr >= 1.5: pts = 12
    elif vr >= 1.2: pts = 6
    else:           pts = 0
    bd["Volume Confirmation"] = {"pts": pts, "max": 20, "val": round(vr, 1)}
    total += pts

    # 3. Near 52-week high — breakout zone (20 pts)
    pfh = tech.get("pct_from_high", -100)   # negative = below high
    if pfh >= -5:    pts = 20
    elif pfh >= -10: pts = 15
    elif pfh >= -20: pts = 8
    else:            pts = 0
    bd["Near 52W High"] = {"pts": pts, "max": 20, "val": f"{pfh:.1f}%"}
    total += pts

    # 4. Relative strength vs SPY (20 pts)
    rs = tech.get("rs_vs_spy", 1.0)
    if rs >= 1.3:   pts = 20
    elif rs >= 1.1: pts = 14
    elif rs >= 1.0: pts = 8
    else:           pts = 0
    bd["RS vs SPY"] = {"pts": pts, "max": 20, "val": round(rs, 2)}
    total += pts

    # 5. VCP pattern (15 pts)
    pts = 15 if tech.get("is_vcp") else 0
    bd["VCP Pattern"] = {"pts": pts, "max": 15, "val": bool(tech.get("is_vcp"))}
    total += pts

    return round(min(total, 100), 1), bd


# ── Long-term investment score ─────────────────────────────────────────────────

def score_investment(tech: dict, fund: dict) -> tuple[float, dict]:
    """
    Looks for: revenue growth, gross margin, debt, EPS trend, room to grow (market cap),
    revenue acceleration.
    """
    bd: dict = {}
    total = 0.0

    # 1. Revenue growth YoY (25 pts)
    rg = fund.get("revenue_growth_yoy")
    if rg is not None:
        if rg >= 40:   pts = 25
        elif rg >= 25: pts = 20
        elif rg >= 15: pts = 12
        elif rg >= 5:  pts = 5
        else:          pts = 0
    else:
        pts = 0
    bd["Revenue Growth YoY"] = {"pts": pts, "max": 25, "val": f"{rg:.1f}%" if rg is not None else "N/A"}
    total += pts

    # 2. Gross margin (20 pts)
    gm = fund.get("gross_margin")
    if gm is not None:
        if gm >= 60:   pts = 20
        elif gm >= 40: pts = 14
        elif gm >= 20: pts = 7
        else:          pts = 2
    else:
        pts = 0
    bd["Gross Margin"] = {"pts": pts, "max": 20, "val": f"{gm:.1f}%" if gm is not None else "N/A"}
    total += pts

    # 3. Debt/equity health (15 pts)
    de = fund.get("debt_equity")
    if de is None:         pts = 7
    elif de < 20:          pts = 15
    elif de < 50:          pts = 10
    elif de < 100:         pts = 5
    else:                  pts = 0
    bd["Debt / Equity"] = {"pts": pts, "max": 15, "val": f"{de:.0f}%" if de is not None else "N/A"}
    total += pts

    # 4. EPS / profit trend (20 pts)
    eps = fund.get("eps_trend", "UNKNOWN")
    eps_map = {"POSITIVE": 20, "IMPROVING": 14, "STABLE": 8, "DECLINING": 2, "NEGATIVE": 0, "UNKNOWN": 5}
    pts = eps_map.get(eps, 5)
    bd["EPS / Profit Trend"] = {"pts": pts, "max": 20, "val": eps}
    total += pts

    # 5. Market-cap room to grow (10 pts)
    mc = fund.get("market_cap") or 0
    if 0 < mc < 500e6:     pts = 10
    elif mc < 2e9:         pts = 8
    elif mc < 10e9:        pts = 5
    elif mc > 0:           pts = 2
    else:                  pts = 3
    bd["Market Cap (Room to Grow)"] = {
        "pts": pts, "max": 10,
        "val": f"${mc/1e9:.1f}B" if mc >= 1e9 else (f"${mc/1e6:.0f}M" if mc else "N/A"),
    }
    total += pts

    # 6. Revenue acceleration (10 pts)
    ra = fund.get("revenue_accel", "UNKNOWN")
    accel_map = {"ACCELERATING": 10, "STABLE": 5, "DECELERATING": 0, "UNKNOWN": 3}
    pts = accel_map.get(ra, 3)
    bd["Revenue Acceleration"] = {"pts": pts, "max": 10, "val": ra}
    total += pts

    return round(min(total, 100), 1), bd


# ── Multibagger composite score ────────────────────────────────────────────────

def score_multibagger(tech: dict, fund: dict) -> tuple[float, dict]:
    """
    Composite of fundamentals (60 pts) + technicals (40 pts).
    Key criteria: rapid revenue growth, high gross margin, clean balance sheet,
    insider buying, low institutional ownership, Stage 2, strong RS.
    """
    bd: dict = {}
    total = 0.0

    # ── Fundamental layer (60 pts) ───────────────────────────────────────────

    # 1. Revenue growth (25 pts)
    rg = fund.get("revenue_growth_yoy")
    if rg is not None:
        if rg >= 40:   pts = 25
        elif rg >= 25: pts = 18
        elif rg >= 15: pts = 10
        else:          pts = 0
    else:
        pts = 0
    bd["Revenue Growth"] = {"pts": pts, "max": 25, "val": f"{rg:.1f}%" if rg is not None else "N/A"}
    total += pts

    # 2. Gross margin (10 pts)
    gm = fund.get("gross_margin")
    if gm is not None:
        if gm >= 60:   pts = 10
        elif gm >= 40: pts = 7
        elif gm >= 20: pts = 3
        else:          pts = 0
    else:
        pts = 0
    bd["Gross Margin"] = {"pts": pts, "max": 10, "val": f"{gm:.1f}%" if gm is not None else "N/A"}
    total += pts

    # 3. EPS trajectory (10 pts)
    eps = fund.get("eps_trend", "UNKNOWN")
    eps_map = {"POSITIVE": 10, "IMPROVING": 7, "STABLE": 3, "DECLINING": 0, "NEGATIVE": 0, "UNKNOWN": 2}
    pts = eps_map.get(eps, 2)
    bd["EPS Trajectory"] = {"pts": pts, "max": 10, "val": eps}
    total += pts

    # 4. Balance sheet (10 pts)
    de = fund.get("debt_equity")
    cr = fund.get("current_ratio")
    if de is None:    pts = 4
    elif de < 50:     pts = 7
    else:             pts = max(0, int(7 - de / 50))
    if cr and cr >= 2.0:
        pts = min(10, pts + 3)
    bd["Balance Sheet Health"] = {
        "pts": pts, "max": 10,
        "val": f"D/E {de:.0f}%" if de is not None else "N/A",
    }
    total += pts

    # 5. Insider activity (10 pts)
    insider = fund.get("insider_buy_signal", "UNKNOWN")
    insider_map = {"BUYING": 10, "NEUTRAL": 5, "UNKNOWN": 3, "SELLING": 0}
    pts = insider_map.get(insider, 3)
    bd["Insider Activity"] = {"pts": pts, "max": 10, "val": insider}
    total += pts

    # 6. Institutional ownership sweet spot (5 pts)
    inst = fund.get("institutional_ownership")
    if inst is None:            pts = 2
    elif 5 <= inst <= 35:       pts = 5   # discovered but not crowded
    elif 35 < inst <= 60:       pts = 2
    else:                       pts = 0
    bd["Institutional Ownership"] = {
        "pts": pts, "max": 5,
        "val": f"{inst:.0f}%" if inst is not None else "N/A",
    }
    total += pts

    # ── Technical layer (40 pts) ─────────────────────────────────────────────

    # 7. Stage 2 alignment (15 pts)
    stage = tech.get("stage", 0)
    if stage == 2:   pts = 15
    elif stage == 1: pts = 5
    else:            pts = 0
    bd["Stage 2 Technical"] = {"pts": pts, "max": 15, "val": f"Stage {stage}"}
    total += pts

    # 8. Relative strength vs SPY (5 pts)
    rs = tech.get("rs_vs_spy", 1.0)
    if rs >= 1.3:   pts = 5
    elif rs >= 1.1: pts = 3
    elif rs >= 1.0: pts = 1
    else:           pts = 0
    bd["Relative Strength vs SPY"] = {"pts": pts, "max": 5, "val": round(rs, 2)}
    total += pts

    # 9. Small/mid-cap sweet spot (5 pts)
    mc = fund.get("market_cap") or 0
    if 50e6 <= mc <= 2e9:   pts = 5
    elif 2e9 < mc <= 5e9:   pts = 3
    else:                   pts = 1
    bd["Market Cap (Multibagger Sweet Spot)"] = {
        "pts": pts, "max": 5,
        "val": f"${mc/1e9:.1f}B" if mc >= 1e9 else (f"${mc/1e6:.0f}M" if mc else "N/A"),
    }
    total += pts

    # 10. Revenue acceleration bonus (5 pts)
    ra = fund.get("revenue_accel", "UNKNOWN")
    accel_map = {"ACCELERATING": 5, "STABLE": 2, "DECELERATING": 0, "UNKNOWN": 1}
    pts = accel_map.get(ra, 1)
    bd["Revenue Acceleration"] = {"pts": pts, "max": 5, "val": ra}
    total += pts

    # ── Red-flag penalty ─────────────────────────────────────────────────────
    flags = check_red_flags(tech, fund)
    if len(flags) >= 2:
        total = max(0, total - 20)
    elif len(flags) == 1:
        total = max(0, total - 8)

    return round(min(total, 100), 1), bd


# ── Master entry point ─────────────────────────────────────────────────────────

def calculate_all_scores(tech: dict, fund: dict) -> dict:
    ss,  ss_bd  = score_swing_short(tech,  fund)
    sm,  sm_bd  = score_swing_medium(tech, fund)
    inv, inv_bd = score_investment(tech,   fund)
    mb,  mb_bd  = score_multibagger(tech,  fund)
    flags       = check_red_flags(tech,    fund)

    return {
        "swing_short_score":  ss,
        "swing_medium_score": sm,
        "investment_score":   inv,
        "multibagger_score":  mb,
        "red_flags":          flags,
        "score_breakdown": {
            "swing_short":  ss_bd,
            "swing_medium": sm_bd,
            "investment":   inv_bd,
            "multibagger":  mb_bd,
        },
    }
