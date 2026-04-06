# PineConnector Use Cases

## Use Case Index

| ID | Use Case | Complexity |
|----|----------|------------|
| UC-01 | Simple market order from TradingView | Basic |
| UC-02 | Market order with SL and TP | Basic |
| UC-03 | Partial profit booking (3 TP levels) | Intermediate |
| UC-04 | Trailing stop on single position | Intermediate |
| UC-05 | Partial TP + trailing after TP2 | Advanced |
| UC-06 | Time-based exit | Basic |
| UC-07 | Risk-based position sizing | Intermediate |
| UC-08 | Multiple strategies on same symbol | Intermediate |
| UC-09 | Close all positions (emergency) | Basic |
| UC-10 | Pending orders (limit/stop) | Basic |
| UC-11 | Signal rejected by risk engine | Basic |
| UC-12 | MT5 disconnection and recovery | Advanced |
| UC-13 | Dry-run testing | Basic |
| UC-14 | Multi-symbol portfolio automation | Advanced |

---

## UC-01: Simple Market Order

**Actor**: TradingView strategy
**Trigger**: Strategy fires `strategy.entry("Long")`

**Alert message:**
```json
{"token":"abc123","action":"buy","symbol":"XAUUSD","lot":0.05}
```

**Flow:**
1. TradingView sends POST to webhook
2. Python parses, authenticates, risk checks pass
3. Signal dispatched to Rust engine
4. Rust sends `place_order` command to MT5 bridge
5. MT5 opens market buy 0.05 lots XAUUSD
6. Result stored in database

**Expected outcome:** Trade opened at market price with no SL/TP.

---

## UC-02: Market Order with SL and TP

**Actor**: TradingView strategy
**Trigger**: Strategy fires entry with plotted SL/TP levels

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0850,
  "tp": 1.0950,
  "comment": "EMA_cross"
}
```

**Flow:**
1-4. Same as UC-01
5. MT5 opens market buy 0.10 lots EURUSD with SL=1.0850, TP=1.0950
6. When price hits TP or SL, MT5 closes automatically (broker-level)

---

## UC-03: Partial Profit Booking

**Actor**: Swing trader
**Trigger**: Entry signal with multi-level profit targets

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.30,
  "sl": 1.0850,
  "tp1": "15@50%",
  "tp2": "30@30%",
  "tp3": "50@20%"
}
```

**Flow:**
1. Order placed: 0.30 lots BUY EURUSD, NO broker TP (Rust manages TPs)
2. Rust monitors price every 100ms tick
3. Price +15 pips: Rust closes 0.15 lots, moves SL to breakeven
4. Python receives state update, sends Telegram: "TP1 hit, 0.15 lots closed"
5. Price +30 pips: Rust closes 0.09 lots
6. Price +50 pips: Rust closes remaining 0.06 lots
7. Position fully closed

**Edge case:** If remaining lot < broker minimum (0.01), Rust closes entire remaining.

---

## UC-04: Trailing Stop

**Actor**: Trend-following strategy
**Trigger**: Entry signal on strong momentum

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "XAUUSD",
  "lot": 0.05,
  "sl": 2280,
  "tp": 2400,
  "trailing": {
    "enabled": true,
    "activation_pips": 30,
    "distance_pips": 15,
    "step_pips": 5
  }
}
```

**Flow:**
1. Order placed with SL=2280, TP=2400
2. Price moves from 2300 to 2330 (+30 pips): trailing activates
3. SL moves to 2330-15=2315
4. Price to 2340: SL moves to 2325 (moved 10 pips >= step of 5)
5. Price retraces to 2332: SL stays at 2325 (never moves backward)
6. Price to 2325: SL hit, position closed at +25 pips profit

---

## UC-05: Partial TP + Trailing After TP2

**Actor**: Professional trader
**Trigger**: High-conviction swing trade

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "GBPUSD",
  "lot": 0.60,
  "sl": 50,
  "partial_tp": {
    "tp1_pips": 20, "tp1_percent": 50,
    "tp2_pips": 40, "tp2_percent": 30,
    "tp3_pips": 100, "tp3_percent": 100,
    "move_sl_to_be_on_tp1": true,
    "trail_after_tp2": true,
    "trail_distance_pips": 20
  }
}
```

**Flow:**
1. Open 0.60 lots, no broker TP
2. +20 pips: close 0.30 lots (50%), SL to breakeven → 0.30 remaining
3. +40 pips: close 0.18 lots (30%), trailing activates → 0.12 remaining
4. Price at +60 pips: trailing SL = +60-20 = +40 pips from entry
5. Price retraces to +40 pips: trailing SL hit, remaining 0.12 lots closed

**Result:** Captured 50% at +20, 30% at +40, 20% at +40 (trailing exit).

---

## UC-06: Time-Based Exit

**Actor**: Day trader
**Trigger**: Intraday strategy that must close before market close

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "NAS100",
  "lot": 0.02,
  "sl": 50,
  "tp": 150,
  "time_exit_minutes": 240,
  "comment": "intraday_only"
}
```

**Flow:**
1. Order placed at 10:00 AM
2. time_exit_at set to 2:00 PM (240 minutes later)
3. If TP/SL not hit by 2:00 PM, Rust auto-closes entire position
4. State update published, Telegram notification sent

---

## UC-07: Risk-Based Position Sizing

**Actor**: Risk-managed portfolio
**Trigger**: Strategy provides SL distance, system calculates lot

**Alert message:**
```json
{
  "token": "abc123",
  "action": "buy",
  "symbol": "EURUSD",
  "risk_percent": 1,
  "sl": 30,
  "tp": 60
}
```

**Calculation (done by risk engine):**
```
Equity: $10,000
Risk: 1% = $100
SL distance: 30 pips
Pip value (EURUSD standard lot): $10/pip
Lot = $100 / (30 * $10) = 0.33 lots
Clamped to max_lot_size (1.0): 0.33 lots
Rounded down to 0.01: 0.33 lots
```

---

## UC-08: Multiple Strategies on Same Symbol

**Actor**: Trader running EMA and RSI strategies on XAUUSD

**Alert 1 (EMA strategy):**
```json
{"token":"abc123","action":"buy","symbol":"XAUUSD","lot":0.05,"sl":30,"tp":60,"magic":1001,"comment":"EMA_15m"}
```

**Alert 2 (RSI strategy):**
```json
{"token":"abc123","action":"sell","symbol":"XAUUSD","lot":0.03,"sl":20,"tp":40,"magic":1002,"comment":"RSI_1h"}
```

**Flow:**
- Both trades open independently on MT5 (different magic numbers)
- Risk engine tracks: 2 open trades for XAUUSD (within max_open_per_symbol)
- Close commands target specific direction: `closebuy` only closes the buy

---

## UC-09: Emergency Close All

**Actor**: Trader during unexpected volatility
**Trigger**: Manual action or automated circuit breaker

**Method 1 — Dashboard button:** Click "Close All" at http://localhost:8003

**Method 2 — API call:**
```bash
curl -X POST http://localhost:8003/api/close-all
```

**Method 3 — Webhook alert:**
```json
{"token":"abc123","action":"closeall","symbol":"ALL"}
```

**Flow:**
1. Signal bypasses risk checks (close commands exempt)
2. Rust iterates ALL managed positions, sends close_order for each
3. MT5 bridge closes all positions
4. Telegram: "Emergency close all executed — 5 positions closed"

---

## UC-10: Pending Orders

**Actor**: Support/resistance trader
**Trigger**: Place limit order at key level

**Buy limit example:**
```json
{
  "token": "abc123",
  "action": "buylimit",
  "symbol": "EURUSD",
  "lot": 0.10,
  "price": 1.0800,
  "sl": 1.0770,
  "tp": 1.0860
}
```

**Flow:**
1. Rust sends pending order to MT5 bridge
2. MT5 places buy limit at 1.0800
3. When price reaches 1.0800, MT5 fills the order
4. If partial TP configured, Rust monitors fill and activates state machine

---

## UC-11: Signal Rejected by Risk Engine

**Actor**: TradingView sending excessive signals
**Trigger**: Strategy fires during high-frequency period

**Scenario:** 21st trade of the day (limit = 20)

**Alert message:**
```json
{"token":"abc123","action":"buy","symbol":"EURUSD","lot":0.1,"sl":30,"tp":60}
```

**Response:**
```json
{
  "status": "rejected",
  "signal_id": "",
  "reason": "Daily trade limit reached (20)"
}
```

**Stored in database:** `signals` table with `risk_passed=0`, `rejection_reason="Daily trade limit reached (20)"`

---

## UC-12: MT5 Disconnection Recovery

**Scenario**: MT5 terminal crashes or network drops

**Flow:**
1. Bridge detects MT5 disconnect
2. Incoming commands queued (up to 50 commands, 30s timeout each)
3. Reconnection attempts every 5s (up to 10 attempts)
4. On reconnect: drain queue, execute pending commands
5. Commands older than 30s: return error result to Rust
6. If all retries exhausted: all queued commands get error results

---

## UC-13: Dry-Run Testing

**Actor**: Developer testing new strategy alerts
**Trigger**: Start server with `--dry-run` flag

```bash
py -3 run.py --dry-run
```

**Behavior:**
- Webhook accepts alerts normally
- Risk checks run normally
- Signal dispatched to Rust with `dry_run=true`
- Rust logs: "DRY RUN — skipping execution for signal_123"
- No commands sent to MT5 bridge
- State updates published (logged but no real trades)
- Dashboard shows "DRY RUN" badge
- Signals saved to database for review

---

## UC-14: Multi-Symbol Portfolio Automation

**Actor**: Portfolio trader with 5 strategies across 5 symbols
**Trigger**: Multiple TradingView alerts firing throughout the day

**Configuration:**
```yaml
# configs/risk.yaml
max_trades_per_day: 30
max_open_per_symbol: 2
max_total_open: 10
max_daily_loss_usd: 1000
```

**Active strategies:**
1. XAUUSD scalp (magic 1001) — 0.05 lots, 20 pip SL/TP
2. EURUSD swing (magic 1002) — 0.20 lots, partial TP
3. GBPUSD breakout (magic 1003) — 0.10 lots, trailing
4. NAS100 momentum (magic 1004) — 0.02 lots, time exit 4h
5. USDJPY mean-revert (magic 1005) — 0.15 lots, fixed SL/TP

**The system handles:**
- Independent risk tracking per symbol
- Up to 10 positions open simultaneously
- Partial TP and trailing running concurrently on different positions
- Daily loss circuit breaker across all positions
- All trades visible on single dashboard
