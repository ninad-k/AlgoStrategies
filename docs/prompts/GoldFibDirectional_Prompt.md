# Gold Fibonacci Directional Strategy - AI Agent Prompt

## Objective
Build a **directional Gold (XAUUSD) strategy** (no hedging) that uses Fibonacci retracement levels (0.44 and 0.50) from multiple timeframes as support/resistance zones. Take BUY or SELL trades based on EMA trend filters and level bounces. One trade at a time.

---

## Strategy Summary

### Instrument & Timeframes
- **Instrument:** XAUUSD (Gold)
- **Analysis Timeframes:** 22-hour chart (monthly levels), 30-minute chart (intraday levels)
- **Execution Timeframe:** M1 (1-minute chart)
- **Level Lookback:** 30 days for 22H levels, 2 days for intraday levels (today + yesterday)

### Core Concept
Identify high-probability support/resistance zones using Fibonacci levels from multiple timeframes. Trade in the direction of the trend (EMA 200) by entering at level bounces. One position at a time — pure directional, no hedging.

---

## Level Calculation Rules

### 1. Monthly Levels (22-Hour Chart)
- **Source:** 22-hour candles starting at 20:00 UTC (one per day)
- **Lookback:** Last 30 candles (1 month)
- **Fib Levels:** For each candle:
  - `fib_044 = high - 0.44 * (high - low)`
  - `fib_050 = (high + low) / 2`
- **Cleanup:** Remove the 30th-day (oldest) entry each day

### 2. Daily Session Levels (30-Minute Chart)

#### a) 23:00 UTC Candle
- Wait for the 23:00 UTC candle to form
- Scan M30 for the **first red (bearish) candle** after 23:00
- Draw Fib on that candle: `fib_044` and `fib_050`

#### b) 07:00 UTC Candle
- Take the M30 candle at 07:00 UTC, draw Fib

#### c) 12:00 UTC Candle
- Take the M30 candle at 12:00 UTC, draw Fib

**Cleanup:** Keep only today's and yesterday's daily levels.

### 3. Overlap / Confluence
- Levels within threshold (e.g., 50 pips) are **overlapping** → higher confidence
- Higher confidence levels are stronger entries

---

## Trade Execution Rules

### Direction Filter (mandatory)
| Condition | Action |
|-----------|--------|
| Price > EMA 200 AND EMA 50 > EMA 200 | BUY only |
| Price < EMA 200 AND EMA 50 < EMA 200 | SELL only |
| Mixed (price on one side, cross on other) | No trade or reduced confidence |

### Entry Conditions — BUY
1. Price is above EMA 200 (bullish bias)
2. Price touches or bounces from a **support level** (fib level below price)
3. Confirmation: bullish candle close above the level
4. Optional: SuperTrend is bullish
5. Higher confidence levels get priority

### Entry Conditions — SELL
1. Price is below EMA 200 (bearish bias)
2. Price touches or rejects from a **resistance level** (fib level above price)
3. Confirmation: bearish candle close below the level
4. Optional: SuperTrend is bearish
5. Higher confidence levels get priority

### Exit Conditions
1. **Take Profit:** Next opposing fib level (resistance for BUY, support for SELL)
2. **Stop Loss:** Previous fib level beyond entry, or SuperTrend value, or fixed pips
3. **SuperTrend flip:** If enabled, exit when SuperTrend changes direction
4. **EMA cross:** Exit if EMA 50 crosses EMA 200 against position
5. **Daily close:** Close position at configurable UTC hour to avoid swap

### Position Management
- **Max 1 trade** at a time
- No re-entry on same level within cooldown period
- Trail stop after configurable profit threshold

---

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Fib Level 1 | 0.44 | First Fibonacci retracement level |
| Fib Level 2 | 0.50 | Second Fibonacci retracement level |
| EMA Fast | 50 | Fast EMA for trend change |
| EMA Slow | 200 | Slow EMA for trend direction |
| SuperTrend Period | 10 | ATR period |
| SuperTrend Multiplier | 3.0 | ATR multiplier |
| Overlap Threshold | 50 pips | Confluence distance |
| 22H Lookback | 30 | Days of 22H candles |
| Lot Size | 0.1 | Position size |
| SL Mode | SuperTrend | Options: SuperTrend, Fixed Pips, Previous Level |
| Fixed SL Pips | 50 | If SL mode is fixed |
| TP Mode | Next Level | Options: Next Level, Fixed Pips, RR Ratio |
| Fixed TP Pips | 100 | If TP mode is fixed |
| RR Ratio | 2.0 | If TP mode is RR |
| Daily Close Hour | 21 | UTC hour to close positions |
| Trail Enable | false | Enable trailing stop |
| Trail Pips | 30 | Trailing distance |
| Cooldown Bars | 10 | Bars before re-entry at same level |

---

## Dashboard
- P&L (session + cumulative)
- Current position direction and lot size
- Next support and resistance with confidence
- Total trades, win rate
- Buy count, sell count
- EMA values, trend direction
- SuperTrend value and direction
- Active level count and breakdown
