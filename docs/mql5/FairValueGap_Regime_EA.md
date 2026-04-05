# FairValueGap_Regime_EA

- **File:** `mql5/experts/FairValueGap_Regime_EA.mq5`  
- **Author:** Ninad K · **Version:** 1.00  

## Purpose

Automated Expert Advisor that **detects Fair Value Gaps (FVG)** on the working timeframe, tracks each zone’s fill state, and **enters on pullback** into an unfilled zone when optional **regime filters** (higher-timeframe EMA trend and/or ADX + directional movement) align. Exits use **ATR or fixed points** for SL/TP, with optional **partial close**, **trailing**, **break-even**, **session filter**, and **daily/total drawdown** caps.

## Fair Value Gap definition (as implemented)

- **Bullish FVG:** `low[i] > high[i-2]` with gap height ≥ minimum points (middle bar `i-1` anchors the zone time span).  
- **Bearish FVG:** `high[i] < low[i-2]` (symmetric).  

Zones are stored in a capped array; duplicates at the same start time and direction are skipped.

## Entry logic (summary)

- Evaluated on **each new bar** using the **last completed bar** (`ratesTotal - 2`).  
- **Long:** bullish zone, price interacts with zone (low in extended zone band), optional bullish confirmation candle, `IsRegimeBullish()`, capacity per direction.  
- **Short:** mirrored for bearish zones.  
- **Margin:** order blocked unless free margin ≥ ~120% of required margin.  
- **One trade per zone** via `isTraded` flag.

## Regime filter

| Mode | Meaning |
|------|--------|
| `REGIME_NONE` | No filter |
| `REGIME_EMA` | HTF: price vs fast/slow EMA stack |
| `REGIME_ADX` | ADX strength + DI+ vs DI− |
| `REGIME_BOTH` | EMA and ADX conditions must pass |

**Note:** Input `InpHTFBiasRequired` is present for future use; current regime logic does not branch on it.

## Risk and trade management

- **Lots:** fixed size or percent-of-balance risk from SL distance.  
- **SL/TP:** ATR multiples or fixed points; distances floored by broker stop level and spread buffer.  
- **Partial:** midpoint of TP distance, or fixed R multiple.  
- **Trailing / BE:** ATR- or points-based, aligned with SL mode.

## Companion indicator

Visual-only zones: `mql5/indicators/FVG_Zones_Indicator.mq5` (same gap rules, rectangles on chart).

## Operational notes

- Forward-test on each symbol; **FOK** filling may not suit all brokers — adjust `SetTypeFilling` if rejects occur.  
- Drawdown limits compare **equity** to stored balance baselines; understand your broker’s reporting window for “daily”.  

See also: `docs/mql5/FVG_Pullback_Strategy.md` for a discretionary ruleset aligned with this logic.
