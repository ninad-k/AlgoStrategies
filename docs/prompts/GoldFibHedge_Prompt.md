# Gold Fibonacci Hedge Strategy - AI Agent Prompt

## Objective
Build a **full-hedge Gold (XAUUSD) strategy** that uses Fibonacci retracement levels (0.44 and 0.50) derived from multiple timeframes to identify support/resistance zones, then manages a hedged position by closing the losing leg when price reaches these levels.

---

## Strategy Summary

### Instrument & Timeframes
- **Instrument:** XAUUSD (Gold)
- **Analysis Timeframes:** 22-hour chart (monthly levels), 30-minute chart (intraday levels)
- **Execution Timeframe:** M1 (1-minute chart)
- **Level Lookback:** 30 days for 22H levels, 2 days for intraday levels (today + yesterday only)

### Core Concept
Maintain a **full hedge** (1 BUY + 1 SELL) at all times during the session. Use Fibonacci-derived support/resistance levels to close the losing leg. If price reverses, re-establish the hedge. Close both positions daily before swap to avoid overnight charges.

---

## Level Calculation Rules

### 1. Monthly Levels (22-Hour Chart)
- **Source:** 22-hour candles starting at 20:00 UTC (one per day)
- **Lookback:** Last 30 candles (1 month)
- **Fib Levels:** For each candle, compute:
  - `fib_044 = high - 0.44 * (high - low)` → upper zone
  - `fib_050 = (high + low) / 2` → midpoint
- **Cleanup:** Remove the 30th-day (oldest) entry each day
- **Purpose:** These are longer-term S/R levels with higher weight

### 2. Daily Session Levels (30-Minute / H1 Chart)
Three specific UTC time candles generate intraday levels:

#### a) 23:00 UTC Candle
- Wait for the 23:00 UTC candle to form
- Then scan M30 chart for the **first red (bearish) candle** after 23:00
- Draw Fib on that red candle: `fib_044` and `fib_050`
- These become the first intraday S/R levels

#### b) 07:00 UTC Candle
- Take the 30-min candle at 07:00 UTC
- Draw Fib: `fib_044` and `fib_050`
- Add as S/R levels

#### c) 12:00 UTC Candle
- Take the 30-min candle at 12:00 UTC
- Draw Fib: `fib_044` and `fib_050`
- Add as S/R levels

**Cleanup:** Keep only today's and yesterday's daily levels. Remove anything older (day-before-yesterday and earlier).

### 3. Level Overlap / Confluence Detection
- When levels from different sources fall within a threshold (e.g., 50 pips / 5.0 points for Gold), they are considered **overlapping**
- Overlapping levels get a **higher confidence rating** (2x, 3x based on number of overlaps)
- High-confidence levels are stronger support/resistance zones

---

## Trade Execution Rules

### Entry Logic
1. **Always open a full hedge** (1 BUY + 1 SELL) when price reaches any Fib level
2. Maximum 2 trades open at any time (1 BUY + 1 SELL)
3. **EMA 200 Filter:**
   - Price above EMA 200 → favor BUY (larger lot on buy leg)
   - Price below EMA 200 → favor SELL (larger lot on sell leg)
4. **EMA 50 Filter:**
   - EMA 50 crossing EMA 200 signals trend change
   - Use to adjust bias direction

### Exit Logic (Losing Leg)
1. When price reaches a Fib level acting as **resistance** → close the BUY (losing) leg
2. When price reaches a Fib level acting as **support** → close the SELL (losing) leg
3. Use the 30-minute timeframe Fib levels for intraday exit decisions
4. Use the 22H levels as stronger confirmation

### Re-Hedge Logic
- After closing the losing leg, if price reverses (moves against the remaining trade), **reopen the hedge**
- Trigger: Price crosses back through the level that caused the exit, or hits the next opposing level

### Daily Reset (Swap Avoidance)
- Close **both** trades before end of day (e.g., 21:00 UTC)
- Reopen hedge positions at start of next session based on current level proximity

### Optional: SuperTrend for TP/SL
- SuperTrend indicator (Period: 10, Multiplier: 3.0) can be used for:
  - **Take Profit:** When SuperTrend flips direction
  - **Stop Loss:** Set SL at SuperTrend value
- This is optional and can be toggled on/off

### Optional: Trailing Stop
- Trail stop loss by a fixed number of pips or by ATR multiple
- Move SL to breakeven after a configurable profit threshold
- Can also trail using SuperTrend value

---

## Filters & Confirmation

| Filter | Purpose | Action |
|--------|---------|--------|
| EMA 200 | Long-term trend | BUY above, SELL below |
| EMA 50 | Trend change detection | Cross signals bias change |
| SuperTrend (optional) | Dynamic TP/SL | Exit on flip, trail with value |
| Level Confidence | Overlap count | Higher confidence = stronger level |

---

## Dashboard Requirements

Display on chart:
1. **P&L** — Current session profit/loss, cumulative P&L
2. **Lot Size** — Current position sizes for BUY and SELL legs
3. **Next S/R Levels** — Nearest support below price, nearest resistance above price, with confidence ratings
4. **Total Trades** — Count of all trades taken today
5. **Buy/Sell Counts** — Separate counts for BUY and SELL trades
6. **Level List** — All active Fib levels with source (22H/23:00/07:00/12:00) and confidence

---

## Level Visualization (Optional Toggle)
- Plot all active Fib levels as horizontal lines on M1 chart
- Color code by source:
  - **22H levels:** Gold/Yellow
  - **23:00 UTC levels:** Orange
  - **07:00 UTC levels:** Cyan
  - **12:00 UTC levels:** Magenta
- Show level value labels
- Highlight overlapping/high-confidence levels with thicker lines

---

## Implementation Platforms
1. **MT5 Indicator** (.mq5) — Plots levels + buy/sell signal arrows
2. **MT5 Expert Advisor** (.mq5) — Full automated hedge strategy
3. **TradingView PineScript** — Strategy with visual levels and alerts

---

## Key Parameters (Configurable)

| Parameter | Default | Description |
|-----------|---------|-------------|
| Fib Level 1 | 0.44 | First Fibonacci retracement level |
| Fib Level 2 | 0.50 | Second Fibonacci retracement level |
| EMA Fast Period | 50 | Fast EMA for trend change |
| EMA Slow Period | 200 | Slow EMA for trend filter |
| SuperTrend Period | 10 | SuperTrend ATR period |
| SuperTrend Multiplier | 3.0 | SuperTrend ATR multiplier |
| Overlap Threshold | 50 pips | Distance to consider levels overlapping |
| 22H Lookback Days | 30 | Number of 22H candles to analyze |
| Lot Size | 0.1 | Base lot size per leg |
| Daily Close Hour (UTC) | 21 | Hour to close all positions |
| Trail Enable | false | Enable trailing stop |
| Trail Pips | 30 | Trailing distance in pips |
| Plot Levels | true | Show level lines on chart |
| Max Trades | 2 | Maximum simultaneous positions |

---

## Risk Management
- Never exceed 2 open positions
- Each leg is hedged — net exposure is minimal
- Daily close eliminates overnight gap risk and swap charges
- Higher confidence levels get priority for trade decisions
- EMA filters prevent trading against the dominant trend
