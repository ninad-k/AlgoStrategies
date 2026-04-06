# PineConnector Risk Management Guide

## Overview

The risk engine is a **zero-I/O, in-memory gate** that processes every incoming signal before it reaches the execution engine. All checks complete in <5ms. The engine is configured via `configs/risk.yaml` and resets daily at the configured UTC hour.

---

## Risk Checks (Execution Order)

Checks run sequentially. First failure stops the pipeline and rejects the signal.

### Check 1: Signal Deduplication

**Purpose**: Prevent duplicate execution from TradingView retries or alert misfires.

**How it works**:
- Hash computed from: `action + symbol + lot + sl + tp`
- Hash stored in a ring buffer (FIFO, max 100 entries)
- If same hash seen within `dedup_window_seconds`, signal rejected

**Config**:
```yaml
dedup_window_seconds: 5    # Time window for duplicate detection
dedup_buffer_size: 100     # Max hashes stored
```

**Rejection message**: `"Duplicate signal within 5s"`

### Check 2: Maximum Lot Size

**Purpose**: Prevent fat-finger errors or oversized positions.

**Config**:
```yaml
max_lot_size: 1.0          # Maximum lot per single trade
```

**Rejection message**: `"Lot 2.0 exceeds max 1.0"`

### Check 3: Maximum Daily Trades

**Purpose**: Cap total number of trades per day to prevent overtrading.

**Config**:
```yaml
max_trades_per_day: 20     # Resets at daily_reset_hour_utc
```

**Rejection message**: `"Daily trade limit reached (20)"`

### Check 4: Maximum Open Trades per Symbol

**Purpose**: Prevent concentration risk on a single instrument.

**Config**:
```yaml
max_open_per_symbol: 3     # Max concurrent positions per symbol
```

**Rejection message**: `"Max open trades for EURUSD (3)"`

### Check 5: Maximum Total Open Trades

**Purpose**: Cap total portfolio exposure.

**Config**:
```yaml
max_total_open: 10         # Max total open positions across all symbols
```

**Rejection message**: `"Max total open trades (10)"`

### Check 6: Trade Cooldown

**Purpose**: Prevent rapid-fire execution on the same symbol (e.g., from indicator noise).

**Config**:
```yaml
cooldown_seconds: 5        # Minimum seconds between trades per symbol
```

**Rejection message**: `"Cooldown: 3.2s remaining for EURUSD"`

### Check 7: Equity Protection

**Purpose**: Daily loss circuit breaker.

**Config**:
```yaml
max_daily_loss_usd: 500.0      # Hard stop in dollar amount
max_daily_loss_percent: 5.0    # Hard stop as % of account equity
```

**Note**: Only enforced when equity is known (updated from MT5 bridge execution results). If equity is unknown (e.g., first trades of the day), this check is skipped.

**Rejection messages**:
- `"Daily loss limit $500 reached"`
- `"Daily loss 5.2% exceeds 5.0%"`

---

## Close Commands Bypass Risk

The following actions **skip all risk checks** because they reduce exposure:
- `closebuy`
- `closesell`
- `closeall`
- `cancel_buylimit`
- `cancel_selllimit`

---

## Risk-Based Position Sizing

When `risk_percent` is provided instead of `lot`, the system calculates:

```
risk_amount = equity * (risk_percent / 100)
lot = risk_amount / (sl_pips * pip_value_per_lot)
lot = min(lot, max_lot_size)
lot = floor(lot, 0.01)      # Round down to nearest 0.01
```

**Example**:
- Account equity: $10,000
- Risk: 1% = $100
- SL: 30 pips on EURUSD
- Pip value per standard lot: $10
- Lot = $100 / (30 * $10) = 0.33 lots

---

## Daily Reset

At `daily_reset_hour_utc` (default 0 = midnight UTC), the following state resets:
- `trades_today` counter → 0
- `daily_pnl` → 0.0
- `last_trade_time` per symbol → cleared

Open trade counts (`open_trades`, `total_open`) do NOT reset — they track live positions.

---

## State Synchronization

The risk engine's state updates from two sources:

1. **On signal acceptance**: `trades_today` incremented, `last_trade_time` recorded
2. **On execution result** (from background consumer):
   - `record_open(symbol)`: increments `open_trades[symbol]` and `total_open`
   - `record_close(symbol, profit)`: decrements counters, adds to `daily_pnl`
   - `update_equity(equity)`: updates current equity from MT5

---

## Configuration File

`configs/risk.yaml`:

```yaml
# Position limits
max_lot_size: 1.0
max_trades_per_day: 20
max_open_per_symbol: 3
max_total_open: 10

# Timing
cooldown_seconds: 5
daily_reset_hour_utc: 0

# Loss protection
max_daily_loss_usd: 500.0
max_daily_loss_percent: 5.0

# Spread filter (enforced by MT5 bridge before execution)
max_spread_points: 30

# Equity-based stop (% of starting equity)
equity_stop_percent: 10.0

# Dedup
dedup_window_seconds: 5
dedup_buffer_size: 100
```

---

## Recommended Configurations

### Conservative (small account, learning):
```yaml
max_lot_size: 0.10
max_trades_per_day: 5
max_open_per_symbol: 1
max_total_open: 3
cooldown_seconds: 30
max_daily_loss_usd: 50.0
max_daily_loss_percent: 2.0
```

### Moderate (funded account):
```yaml
max_lot_size: 0.50
max_trades_per_day: 15
max_open_per_symbol: 2
max_total_open: 6
cooldown_seconds: 10
max_daily_loss_usd: 300.0
max_daily_loss_percent: 3.0
```

### Aggressive (prop firm, high frequency):
```yaml
max_lot_size: 2.0
max_trades_per_day: 50
max_open_per_symbol: 5
max_total_open: 20
cooldown_seconds: 2
max_daily_loss_usd: 1000.0
max_daily_loss_percent: 5.0
```
