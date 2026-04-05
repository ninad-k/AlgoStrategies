# MACrossover_Filtered_EA

Expert Advisor: `mql5/experts/MACrossover_Filtered_EA.mq5`  
Author: Ninad K · Version 1.07

## Purpose

Automated trading based on a **fast vs slow moving average crossover** on the chart’s timeframe. Entries can be **filtered** by comparing price to a moving average on a **higher timeframe**. Position size scales with **account equity** (with a dedicated rule for gold symbols), with optional **stop loss**, **take profit**, and **exit on cross back through the fast MA**.

## Behaviour summary

| Area | Behaviour |
|------|-----------|
| **Signal** | Bullish: prior bar’s close above fast MA, fast crossed above slow between bars 2→1, optional filter (close above filter MA). Bearish: mirrored conditions. |
| **Timing** | Logic runs once per **new bar** (`IsNewBar`), using bar index **1** for close and MA values (completed bar). |
| **Reversal** | On a new signal in the opposite direction, the EA **closes** the existing opposite position before opening. |
| **Sizing** | Non-gold: `lot = min(equity / 10000, maxLotSize)`, then normalized to broker min/step/max. Gold (`XAU`/`GOLD`): fixed **0.01** lot. |
| **Stops** | SL/TP distances are specified in **pips** (scaled via `GetPointValue` for 3/5-digit quotes and metals). Distances respect **SYMBOL_TRADE_STOPS_LEVEL** (with a fallback minimum). |
| **Filter** | When `use_ma_filter` is true, `iMAOnArray` computes the filter MA on `timeframe_ma_filter` from copied closes (SMA, EMA, SMMA, or LWMA). |

## Inputs (groups)

- **Chart MA**: `mode_ma`, `period_ma_fast`, `period_ma_slow` — crossover pair on the current chart period.
- **Optional MTF filter**: `use_ma_filter`, `mode_ma_filter`, `timeframe_ma_filter`, `period_ma_filter`.
- **Risk and exits**: `takeProfit`, `stopLoss` (pips), `useFastMAexit`, `maxLotSize`, `minEquity`.
- **Expert**: `MagicNumber` — must be unique per EA instance on the symbol.

## Operational notes

- Requires **fast period &lt; slow period** and valid risk inputs; otherwise `OnInit` fails with an alert.
- Only manages positions whose **symbol** and **magic** match this EA.
- Forward tests should confirm **slippage**, **fill quality**, and that **pip** interpretation matches your broker’s digits for each symbol class.

## Related files

- MQL5 Trade library: `#include <Trade\Trade.mqh>`
