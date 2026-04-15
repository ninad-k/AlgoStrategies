# SuperTrend Flat Breakout + 23 EMA Strategy - AI Agent Prompt

## Objective
Build a **swing trading strategy** for Indian equities (cash segment) that uses SuperTrend flat consolidation as a setup detector and swing-high breakout as the entry trigger. The 23-period EMA provides momentum-based trailing exit. Long only. One position per stock.

---

## Strategy Summary

### Instrument & Markets
- **Instruments:** Indian equities (NSE/BSE), mid-to-large cap (market cap > INR 5,000 Cr)
- **Avoid:** Ultra-large caps (limited momentum), F&O stocks (manipulation risk)
- **Preference:** Stocks near 52-week low transitioning from downtrend to uptrend
- **Chart Timeframe:** Daily (primary), 1-Hour (alternative entry)

### Core Concept
Detect when a stock's SuperTrend shifts from bearish (red) to bullish (green), then wait for the SuperTrend line itself to flatten (consolidation). Mark the swing high during the flat zone and enter on a breakout above it. Trail with the 23 EMA for momentum capture. The strategy limits downside by only entering after consolidation confirmation and provides natural trailing via the EMA.

---

## Indicator Setup

### SuperTrend
- **Period (ATR Length):** 10
- **Multiplier:** 3.0
- **Settings:** Default — no modifications required
- **Purpose:** Trend direction filter + flat consolidation detection

### Exponential Moving Average
- **Length:** 23 periods (approximate trading sessions in one month)
- **Purpose:** Momentum trailing stop — exit when price closes below

---

## Phase 1: Watchlist Generation

### SuperTrend Color Shift (RED to GREEN)
1. Monitor stocks for SuperTrend direction change: RED (bearish) → GREEN (bullish)
2. On the first bar where SuperTrend turns green, add the stock to the **watchlist**
3. No entry yet — this is only a signal to begin monitoring

### Optional Scanner Filter
- SuperTrend bullish breakout (10, 3)
- Stock trading within 10–15% of 52-week low
- Market cap > INR 5,000 Cr

---

## Phase 2: Flat Detection

### SuperTrend Flat Zone Rules
1. After GREEN shift, monitor the SuperTrend **line value** (not price) for flatness
2. **Flat definition:** SuperTrend value changes by less than a small tolerance (e.g., < 0.1% of price) between consecutive bars
3. **Minimum flat duration:** 5 consecutive trading days
4. SuperTrend must remain GREEN throughout the flat period
5. An "uneven" or "jagged" SuperTrend line does NOT qualify — the line must be visually flat

### Swing High Identification
- During the flat zone, record the **highest high** across all bars in the flat period
- This becomes the **breakout level** (resistance)
- If two resistance levels exist within 2–3% of each other, prefer the higher one

---

## Phase 3: Entry Rules

### Primary Entry (Daily Chart)
| Condition | Requirement |
|-----------|-------------|
| SuperTrend | GREEN and flat for ≥ 5 days |
| Breakout candle | Daily GREEN candle closes above swing high |
| Candle quality | Close is above the resistance level (not just a wick) |
| SuperTrend status | Still GREEN at time of entry |

### Retest Entry (missed breakout)
- If the breakout candle moves > 3% above the swing high level on the day of breakout:
  - Do NOT chase
  - Wait for a pullback/retest into the **breakout level + 3%** zone
  - Enter if price retests this zone and holds
  - Example: breakout at 178, retest zone = 178 to ~183.5

### Alternative Intraday Entry (1-Hour Chart)
- If you cannot monitor during the day, convert to 1-hour chart on breakout day
- Enter when a **proper green 1-hour candle** closes above the resistance level
- "Proper" means: the majority of the candle body (> 40–50%) is above the resistance
- A thin wick poking above does NOT count as a valid breakout on 1H

---

## Phase 4: Exit Rules

### Mode A — Target-Based Swing (Fixed Targets)
| Target | Level | Expected Duration |
|--------|-------|-------------------|
| TP1 | Entry + 10% | 1–2 months |
| TP2 | Entry + 20% | 1–2 months |

- Book partial at TP1, remainder at TP2
- Typical holding period: 1.5 to 2 months

### Mode B — Momentum Trailing (23 EMA)
1. Hold position as long as price stays **above** the 23 EMA
2. Exit when a **daily red candle closes below** the 23 EMA
3. This mode can capture moves far beyond 20% in strong trends
4. Example from transcript: entry at 178, momentum exit at ~300 (~68% gain in ~2 months)

### Mode C — Combined
- Book partial profit at TP1 (10%)
- Trail remainder with 23 EMA
- Exit all on 23 EMA break

---

## Stop Loss Rules

### Initial Stop Loss
- Set at the **most recent small support** level, which will typically be near or below the 23 EMA
- This is the swing low just before or during the flat zone
- Expected risk: typically 5–7% from entry (rarely more)

### Trailing Stop Loss
- After the stock gains 10–12% from entry, shift the stop to the **23 EMA**
- The 23 EMA then serves as both trailing stop and momentum filter
- Exit if daily close falls below 23 EMA

### Maximum Loss Expectation
- Even in worst cases (entry on an invalid signal), loss is capped at ~5%
- The flat-zone + breakout filter prevents most bad entries

---

## Re-entry Rules

### Conditions for Re-entry
- **Only applies** during a downtrend-to-uptrend transition (the initial setup)
- If stop loss is hit shortly after entry AND the stock continues upward:
  1. Identify the **wave** (swing) that triggered the stop loss hit
  2. Mark the **high of that wave**
  3. Re-enter when price breaks above that wave's high on a daily close basis

### When NOT to Re-enter
- Do NOT re-enter if the trailing 23 EMA stop was hit during an established uptrend
- The trailing EMA exit is a profit-taking signal, not a re-entry setup
- A fresh setup (RED → GREEN → flat → breakout) is needed for the next trade

---

## Capital Management

| Parameter | Value |
|-----------|-------|
| Max concurrent positions | 5–7 stocks |
| Allocation per stock | Equal weight (e.g., INR 1L each for INR 5L capital) |
| Total capital deployed | Up to 100% across 5–7 positions |
| Review cycle | 6 months minimum before evaluating strategy performance |

---

## Key Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| ST Period | 10 | 7–14 | SuperTrend ATR period |
| ST Multiplier | 3.0 | 2.0–4.0 | SuperTrend ATR multiplier |
| EMA Length | 23 | 20–25 | Exponential moving average for trailing |
| Min Flat Days | 5 | 3–7 | Minimum days SuperTrend must be flat |
| Flat Tolerance | 0.1% | 0.05–0.2% | Max % change in ST value to count as flat |
| Breakout Buffer | 0% | 0–1% | Buffer above swing high for entry |
| Retest Zone | 3% | 2–5% | Max distance from breakout for retest entry |
| TP1 | 10% | 5–15% | First profit target |
| TP2 | 20% | 15–30% | Second profit target |
| TP1 Qty | 50% | 30–70% | Quantity to close at TP1 |
| Trail Activation | 10% | 8–15% | Gain % before shifting SL to 23 EMA |
| Max Positions | 5 | 3–7 | Maximum concurrent stock positions |

---

## Dashboard Requirements
- Current stage: Watchlist / Flat Detection / Awaiting Breakout / In Position / Trailing
- Entry price, current price, unrealized P&L %
- Days in flat zone (counter)
- Swing high level (breakout target)
- 23 EMA value and distance from price
- Stop loss level and risk %
- TP1/TP2 levels and status (hit/pending)
- SuperTrend direction and value
- Trade count, win rate, profit factor, max drawdown
