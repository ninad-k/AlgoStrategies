# SupportResistance_EA

- **File:** `mql5/experts/SupportResistance_EA.mq5`
- **Author:** Ninad Sanjay Kulkarni · **Version:** 1.00
- **Reference instrument / timeframe:** EUR/USD · H1

## Purpose

Automated Expert Advisor that trades price reactions at **support and resistance zones** on the working timeframe. It combines a **reversal** playbook (bounce off the zone with RSI + candlestick confirmation) with a **breakout-and-retest** playbook (close beyond the zone, then confirm on a pullback). One live trade at a time by default.

## Strategy at a glance

| Aspect | Rule |
|--------|------|
| **Instrument** | EUR/USD (reference). Works on any FX pair with appropriate digit handling. |
| **Timeframe** | Chart timeframe, signals evaluated on the **last completed bar**. |
| **Styles** | Reversal and Breakout (either or both can be enabled). |
| **Max positions** | `InpMaxTrades` (default 1) per symbol/magic. |

## Zone detection

Two modes, selected by `InpUseSwingSR`:

| Mode | Rule |
|------|------|
| **Simple (lookback)** | `resistance = highest high`, `support = lowest low` across `InpLookback` bars (default 50). |
| **Swing-based (default)** | Scan the lookback window for swing highs / swing lows confirmed by `InpSwingLeftRight` bars on each side; take the highest swing-high and lowest swing-low. |

Around each level, a **zone buffer** of `InpZoneBuffer` pips (default 8) defines the reaction band. Pip value adapts to 3- and 5-digit FX quotes (1 pip = 10 points).

## Confirmation signals

- **RSI** (period `InpRSIPeriod`, default 14) evaluated on bar 1:
  - Oversold below `InpRSIOversold` (30) for reversal buys.
  - Overbought above `InpRSIOverbought` (70) for reversal sells.
- **Candlestick patterns** on the last completed bar:
  - **Engulfing** — current bar fully engulfs the prior bar’s body in the opposite direction.
  - **Pin bar** — small body (`≤ InpPinBarMaxBody` of range), dominant wick (`≥ InpPinBarRatio × body`), opposing wick ≤ 50% of dominant wick.
- Either or both patterns can be enabled.

## Entry logic

### Reversal Buy
- `prev bar low` inside support zone `[support − buffer, support + buffer]`.
- RSI(1) < oversold.
- Bullish engulfing **or** bullish pin bar on bar 1.
- Blocked while a breakout retest is pending.

### Reversal Sell
- `prev bar high` inside resistance zone.
- RSI(1) > overbought.
- Bearish engulfing **or** bearish pin bar on bar 1.
- Blocked while a breakout retest is pending.

### Breakout — two-step confirmation
1. **Break detected:** prior completed bar closes beyond the level while the bar before it was still inside. The EA flags a pending retest (BUY above resistance, SELL below support).
2. **Retest window:** up to `InpBreakoutBars` bars to see the broken level tested from the opposite side (buffer × 1.5 on the outside, buffer × 1 on the inside).
3. **Confirmation:** a pattern in the breakout direction, **or** a strong bar (close beyond open and beyond midpoint) in that direction.
4. **Timeout:** if no retest+confirm within `InpBreakoutBars`, the pending breakout is cancelled.

## Exits

| Component | Rule |
|-----------|------|
| **Reversal SL** | `support − InpRevStopLoss` pips (buy) / `resistance + InpRevStopLoss` pips (sell). Default 20. |
| **Reversal TP** | Fixed pips via `InpRevTakeProfit` (when > 0), else Risk:Reward of `InpRevRiskReward` (default 2.0). |
| **Breakout SL** | Beyond the retest bar’s extreme by `InpBreakStopLoss` pips (default 15). |
| **Breakout TP** | Risk:Reward only (`InpBreakRiskReward`, default 2.0). |

All orders pass through `CTrade` with SL/TP sanity checks (SL on the correct side of Ask/Bid, TP likewise) before submission.

## Risk management

- **Sizing:** fixed `InpLotSize` (default 0.1). No percent-risk sizing in this version.
- **Max trades:** `InpMaxTrades` positions matching `_Symbol` + `InpMagicNumber`.
- **Slippage:** `InpSlippage` points on the `CTrade` deviation.
- **Filling mode:** auto-picks `FOK`, `IOC`, or `RETURN` based on broker capabilities.

## Inputs (groups)

| Group | Key inputs |
|-------|-----------|
| **Support & Resistance** | `InpLookback`, `InpZoneBuffer`, `InpUseSwingSR`, `InpSwingLeftRight`, `InpShowSRLines` |
| **RSI** | `InpRSIPeriod`, `InpRSIOversold`, `InpRSIOverbought` |
| **Pattern** | `InpUseEngulfing`, `InpUsePinBar`, `InpPinBarRatio`, `InpPinBarMaxBody` |
| **Reversal** | `InpTradeReversal`, `InpRevStopLoss`, `InpRevTakeProfit`, `InpRevRiskReward` |
| **Breakout** | `InpTradeBreakout`, `InpBreakoutBars`, `InpBreakStopLoss`, `InpBreakRiskReward` |
| **Risk** | `InpLotSize`, `InpMaxTrades`, `InpMagicNumber` |
| **General** | `InpTradeComment`, `InpSlippage` |

## Chart visualization

When `InpShowSRLines` is true the EA draws:

- Horizontal **support** line (green) and **resistance** line (red).
- Filled **zone rectangles** with buffer depth.
- An **info panel** (top-left) showing support/resistance, RSI, price, open trades, and the breakout retest counter when active.

Equity / balance are also printed via `Comment()` for quick inspection during live testing.

## Operational notes

- Processes once per **new bar** using the last completed bar (index 1) to avoid repaint and intrabar noise.
- When both Reversal and Breakout are enabled, a pending breakout retest temporarily blocks new reversal entries so that a broken zone is not simultaneously treated as support and resistance.
- Designed as a **learning/reference** implementation — forward-test per broker before any live use, and verify pip interpretation for non-FX instruments.

## Related files

- MQL5 Trade library: `#include <Trade\Trade.mqh>`
- Position / symbol helpers: `#include <Trade\PositionInfo.mqh>`, `#include <Trade\SymbolInfo.mqh>`
