# FVG pullback strategy (aligned with FairValueGap_Regime_EA)

**Author:** Ninad K  

This document describes a **rules-based trading approach** that matches the EA’s core idea: trade **retests of imbalance (Fair Value Gap) zones** only when **trend and volatility filters** agree. It is **not** a guarantee of profit; all live and simulated results depend on market conditions, execution, costs, and settings.

---

## 1. Concept

- An **FVG** is a three-candle **price inefficiency**: price later often revisits the gap (“mitigation” or “fill”).  
- The EA and indicator use the **same geometric definition** (bullish vs bearish gap between bar `i-2` and bar `i`).  
- **Edge hypothesis** (to validate in backtests): directional trades from **unfilled** zones in the **direction of the higher-timeframe trend** perform better than trading every gap.

---

## 2. When to favour longs vs shorts

| Bias | Conditions (conceptually) |
|------|---------------------------|
| **Long** | HTF structure: fast EMA above slow EMA, price above fast EMA; ADX above minimum with DI+ dominating; **bullish FVG** pullback entry. |
| **Short** | Mirror: fast below slow, price below fast; ADX with DI− dominating; **bearish FVG** pullback. |

Avoid taking both directions aggressively when regime reads **neutral / ranging** — the EA’s regime strings reflect EMA/ADX disagreement.

---

## 3. Suggested parameter “baseline” (starting point only)

Use **symbol-specific optimization**; these are a **conservative starting grid** for liquid FX on ~H1 with **H4** HTF EMA:

| Group | Suggestion |
|-------|------------|
| Regime | `REGIME_BOTH`, HTF **H4**, EMA 50 / 200, ADX min ~20–25 |
| FVG size | Minimum gap points above symbol noise (widen for volatile pairs) |
| SL / TP | ATR mode **1.5× ATR** SL, **3.0× ATR** TP (rough **1:2** RR before partials) |
| Partials | Mid-TP partial + trail remainder (captures runners, reduces full reversal pain) |
| Risk | **1%** risk per trade (`LOT_RISK`), **max open trades** low (1–3) |
| Session | Enable session filter if news/spread spikes hurt fills (e.g. major FX: London/NY overlap) |

**Gold / indices / crypto:** re-tune points, ATR periods, and gap minimum; consider **fixed points** SL/TP if ATR is unstable.

---

## 4. Discipline checklist

1. **Confirm** zone on the **indicator** before trusting automation.  
2. **Cap** daily and total drawdown in line with account tolerance.  
3. **Journal** each trade: regime, zone, SL/TP, outcome — refine filters from data, not hope.  
4. **Re-validate** after major broker or leverage changes.

---

## 5. Disclaimer

Trading involves substantial risk of loss. Past backtest or hypothetical performance does not predict future results. This strategy description is educational and describes the EA’s design intent, not investment advice.
