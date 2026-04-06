# PineConnector Features & Parameters Guide

**Version**: 1.0
**Last Updated**: April 2026

This guide explains all features, parameters, and configuration options available in Rey Capital's PineConnector trading automation platform.

---

## Table of Contents

1. [Core Features](#core-features)
2. [Signal Parameters](#signal-parameters)
3. [Trade Actions](#trade-actions)
4. [Risk Management Parameters](#risk-management-parameters)
5. [Partial Take Profit Configuration](#partial-take-profit-configuration)
6. [Trailing Stop Configuration](#trailing-stop-configuration)
7. [Alert Formats](#alert-formats)
8. [Dashboard Features](#dashboard-features)
9. [Performance Metrics](#performance-metrics)
10. [Advanced Configuration](#advanced-configuration)

---

## Core Features

### 1. **Hybrid Architecture (Python + Rust)**
- **Python FastAPI Backend**: Webhook reception, risk management, database operations
- **Rust Trade Engine**: Ultra-low latency execution with async/await and OS-level threading
- **ZMQ Inter-Process Communication**: 4 independent channels (signal, command, result, state)
- **Multiple MT5 Bridge Modes**:
  - Python MetaTrader5 package (direct DLL integration)
  - MQL5 Expert Advisor (socket-based communication)

### 2. **Multi-Level Partial Take Profits (TP)**
Automatically close portions of your position at different price levels:
- **TP1**: First level (e.g., 50% of lot at +10 pips)
- **TP2**: Second level (e.g., 30% of lot at +20 pips)
- **TP3**: Final level (e.g., 20% of lot at +40 pips)
- **State Machine**: 6-state FSM for reliable execution
- **Breakeven Protection**: Move SL to entry price on TP1 hit
- **Post-TP2 Trailing**: Optional trailing stop after TP2 hit

### 3. **Trailing Stop Management**
- **Profit-Based Activation**: Starts trailing after X pips of profit
- **Step Enforcement**: Minimum movement between SL updates
- **Direction-Aware**: Works for both BUY and SELL positions
- **Peak Tracking**: Remembers highest profit achieved

### 4. **Time-Based Exit (Auto-Close)**
- Automatically close position after specified duration
- Example: `time_exit_minutes: 60` closes after 1 hour
- Useful for intraday strategies

### 5. **Risk Management Gates**
- **Deduplication**: Ignore duplicate signals within 30 seconds
- **Lot Size Validation**: Enforce min/max lot constraints
- **Daily Trade Limit**: Max 20 trades per day (configurable)
- **Max Open Per Symbol**: Prevent over-exposure
- **Cooldown Period**: Minimum time between trades per symbol
- **Equity Protection**: Stop trading if drawdown exceeds threshold
- **Daily PnL Limits**: Stop trading on daily loss limit

### 6. **Multi-Instance Support**
- Run multiple PineConnector instances simultaneously
- Each instance has unique magic number and token
- Ideal for running multiple strategies

### 7. **Paper Trading (Dry-Run Mode)**
- Test strategies without risking real money
- All signals processed normally, but MT5 execution skipped
- Perfect for backtesting and validation
- Enable with: `python run.py --dry-run`

### 8. **Real-Time Dashboard**
- Live trade monitoring with Rey Capital branding
- Dark/Light theme toggle
- Trade history with PnL visualization
- Performance analytics and metrics
- System health indicators

### 9. **Webhook Integration**
- TradingView native support
- JSON and plain text formats
- Token-based authentication
- Multiple auth methods (header, query param, body)

### 10. **Database Persistence**
- SQLite (development) or PostgreSQL (production)
- Permanent trade history
- Historical analytics and reporting
- Trade state recovery on restart

### 11. **Telegram Notifications**
- Real-time trade alerts
- Trade entry, TP hits, exit notifications
- System alerts and errors
- Fire-and-forget, non-blocking

### 12. **Emoji Status Indicators**
- **✅ OK**: System healthy, live trading
- **🟡 DRY RUN**: Paper trading mode
- **⚠️ ERROR**: System issue or disconnected

---

## Signal Parameters

All trade signals must include the action and symbol. Other parameters have sensible defaults.

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `action` | string | Trade action (see Trade Actions table) | `"buy"` |
| `symbol` | string | Trading symbol | `"EURUSD"` |

### Optional Position Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `lot` | float | 0.01 | Trade volume in units | `0.10` |
| `sl` | float | 0 | Stop loss price (absolute) | `1.0850` |
| `tp` | float | 0 | Take profit price (absolute) | `1.0950` |
| `sl_pips` | float | 0 | Stop loss in pips (relative) | `50` |
| `tp_pips` | float | 0 | Take profit in pips (relative) | `50` |
| `price` | float | 0 | Entry price for pending orders | `1.0900` |
| `comment` | string | `""` | Trade comment (visible in MT5) | `"my_strategy"` |
| `magic` | int | 0 | Magic number (strategy identifier) | `1001` |

### Risk Calculation Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `risk_percent` | float | 0 | Risk percentage of account (overrides lot) | `2.0` |
| `risk_amount` | float | 0 | Risk amount in USD (overrides lot) | `100.00` |

### Advanced Exit Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `time_exit_minutes` | int | 0 | Auto-close after N minutes (0 = disabled) | `60` |

### Partial TP Shorthand

Quick syntax for partial take profits (plain text format):

```
tp1=10@50%, tp2=20@30%, tp3=40@20%
```

Means:
- Close 50% at +10 pips
- Close 30% at +20 pips
- Close 20% at +40 pips

---

## Trade Actions

### Market Orders

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `buy` | Market buy (open long) | symbol |
| `sell` | Market sell (open short) | symbol |

### Pending Orders

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `buylimit` | Buy limit order | symbol, price |
| `selllimit` | Sell limit order | symbol, price |
| `buystop` | Buy stop order | symbol, price |
| `sellstop` | Sell stop order | symbol, price |

### Close Positions

| Action | Description | Effect |
|--------|-------------|--------|
| `closebuy` | Close all BUY positions for symbol | Closes all long positions |
| `closesell` | Close all SELL positions for symbol | Closes all short positions |
| `closeall` | Close all open positions (emergency) | Closes everything immediately |

### Position Management

| Action | Description | Parameters |
|--------|-------------|------------|
| `modify` | Modify SL/TP of existing position | symbol, sl, tp |
| `breakeven` | Move SL to entry price (risk-free) | symbol |
| `trailing` | Enable/update trailing stop | symbol, trailing params |
| `cancel_buylimit` | Cancel pending buy limit | symbol |
| `cancel_selllimit` | Cancel pending sell limit | symbol |

---

## Risk Management Parameters

### Configuration File (config.yaml)

```yaml
risk_management:
  # Deduplication
  dedup_window_seconds: 30

  # Lot constraints
  min_lot: 0.01
  max_lot: 10.0

  # Daily limits
  max_trades_per_day: 20
  max_open_per_symbol: 5

  # Cooldown
  cooldown_seconds: 0

  # Equity protection
  max_drawdown_percent: 10.0
  daily_loss_limit: 500.0

  # Enable/disable
  enabled: true
```

### Gate Descriptions

#### 1. **Deduplication (Dedup)**
Prevents identical signals sent multiple times.
- **Window**: Last 30 seconds of signals stored
- **Matching**: action + symbol + lot
- **Purpose**: Avoid duplicate fills on webhook retries
- **Status**: `"rejected"` if duplicate found

#### 2. **Lot Size Gate**
Validates position size constraints.
- **Min Lot**: 0.01 units (minimum in MT5)
- **Max Lot**: 10.0 units (configurable per broker)
- **Purpose**: Prevent overleveraging
- **Status**: `"rejected"` if lot out of bounds

#### 3. **Daily Trade Limit**
Limits total trades opened per day.
- **Default**: 20 trades/day
- **Reset**: Daily at 00:00 UTC
- **Purpose**: Prevent overtrading
- **Status**: `"rejected"` if limit exceeded

#### 4. **Max Open Per Symbol**
Prevents over-concentration in single symbol.
- **Default**: 5 concurrent positions per symbol
- **Applies To**: Open + partial trades
- **Purpose**: Risk diversification
- **Status**: `"rejected"` if limit exceeded

#### 5. **Cooldown Period**
Minimum time between trades for same symbol.
- **Default**: 0 seconds (disabled)
- **Timer**: Per symbol
- **Purpose**: Avoid rapid-fire entries
- **Example**: Set to 300 seconds (5 minutes) to space out entries
- **Status**: `"rejected"` if cooldown active

#### 6. **Equity Protection**
Stops trading if account drawdown exceeds limit.
- **Max Drawdown**: 10% of peak equity
- **Calculation**: (peak_equity - current_equity) / peak_equity
- **Purpose**: Capital preservation
- **Status**: `"rejected"` with reason `"Equity protection triggered"`

#### 7. **Daily PnL Limit**
Stops trading if daily loss exceeds limit.
- **Daily Loss Limit**: $500 (configurable)
- **Reset**: Daily at 00:00 UTC
- **Purpose**: Risk containment
- **Status**: `"rejected"` if limit exceeded

---

## Partial Take Profit Configuration

### Overview
Automatically close portions of your position at different price levels with optional breakeven protection and post-TP2 trailing.

### JSON Format

```json
{
  "partial_tp": {
    "tp1_pips": 10,
    "tp1_percent": 50,
    "tp2_pips": 20,
    "tp2_percent": 30,
    "tp3_pips": 40,
    "tp3_percent": 100,
    "move_sl_to_be_on_tp1": true,
    "trail_after_tp2": false,
    "trail_distance_pips": 10
  }
}
```

### Plain Text Format

```
buy,EURUSD,lot=0.10,sl=1.0850,tp1=10@50%,tp2=20@30%,tp3=40@20%
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tp1_pips` | float | 0 | First TP distance in pips |
| `tp1_percent` | float | 50 | Lot % to close at TP1 |
| `tp2_pips` | float | 0 | Second TP distance in pips |
| `tp2_percent` | float | 30 | Lot % to close at TP2 |
| `tp3_pips` | float | 0 | Third TP distance in pips |
| `tp3_percent` | float | 100 | Lot % to close at TP3 (must be 100 or remaining) |
| `move_sl_to_be_on_tp1` | bool | true | Move SL to breakeven when TP1 hits |
| `trail_after_tp2` | bool | false | Enable trailing after TP2 hit |
| `trail_distance_pips` | float | 10 | Trailing distance if enabled |

### State Machine Diagram

```
Inactive
    ↓ [Signal received]
WaitingTP1
    ↓ [TP1 price hit]
TP1Hit (close tp1_percent)
    ↓ [SL moved to breakeven, wait for TP2]
WaitingTP2
    ↓ [TP2 price hit]
TP2Hit (close tp2_percent)
    ↓ [trail_after_tp2 enabled?]
    └─→ Trailing Stop Active
        ↓ [SL hit or TP3 hit]
WaitingTP3
    ↓ [TP3 price hit]
Complete (close remaining lot)
```

### Example Scenarios

**Scenario 1: Aggressive Scaling**
```json
"tp1_pips": 5, "tp1_percent": 20,
"tp2_pips": 15, "tp2_percent": 30,
"tp3_pips": 30, "tp3_percent": 100
```
- Close 20% at +5 pips (quick profit)
- Close 30% at +15 pips
- Close remaining 50% at +30 pips

**Scenario 2: Breakeven Protection**
```json
"tp1_pips": 10, "tp1_percent": 30,
"tp2_pips": 20, "tp2_percent": 70,
"move_sl_to_be_on_tp1": true
```
- Close 30% at +10 pips
- Move SL to entry (risk-free)
- Close remaining 70% at +20 pips

**Scenario 3: Trailing After Profit**
```json
"tp1_pips": 10, "tp1_percent": 50,
"tp2_pips": 20, "tp2_percent": 50,
"trail_after_tp2": true,
"trail_distance_pips": 5
```
- Close 50% at +10 pips
- Close 50% at +20 pips
- Switch to trailing stop (5 pips behind price)

---

## Trailing Stop Configuration

### Overview
Automatically move SL upward as price moves in your favor, locking in profits.

### JSON Format

```json
{
  "trailing": {
    "enabled": true,
    "activation_pips": 20,
    "distance_pips": 10,
    "step_pips": 1
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | false | Activate trailing stop |
| `activation_pips` | float | 20 | Pips of profit before trailing starts |
| `distance_pips` | float | 10 | Distance to keep SL behind price |
| `step_pips` | float | 1 | Minimum SL movement per update |

### How It Works

1. **Activation**: Once trade is +20 pips in profit, trailing becomes active
2. **Tracking**: SL moves up (for buy) or down (for sell) as price moves favorably
3. **Distance**: SL always stays 10 pips away from current price
4. **Step**: SL only moves if price movement ≥ 1 pip (prevents over-updating)

### Example

**BUY Position with Trailing Stop**
```
Entry: 1.0900
SL: 1.0850
Trailing config: activation=20 pips, distance=10 pips, step=1 pip

Price: 1.0920 (+20 pips) → Trailing activates
  SL: 1.0910 (price - 10 pips)

Price: 1.0925 (+25 pips)
  SL: 1.0915 (price - 10 pips, moved by 5 pips)

Price: 1.0930 (+30 pips)
  SL: 1.0920 (price - 10 pips, moved by 5 pips)

Price: 1.0925 (-5 pips) [SL hit]
  → Position closed at 1.0920 (profit: +20 pips)
```

---

## Alert Formats

### JSON Format (TradingView JSON)

```json
{
  "token": "your_secret_token",
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0850,
  "tp": 1.0950,
  "comment": "my_strategy",
  "magic": 1001,
  "time_exit_minutes": 60,
  "partial_tp": {
    "tp1_pips": 10,
    "tp1_percent": 50
  },
  "trailing": {
    "enabled": true,
    "activation_pips": 20,
    "distance_pips": 10
  }
}
```

### Plain Text Format (Comma-Separated)

```
token,action,symbol,lot=0.10,sl=1.0850,tp=1.0950,comment=strategy
```

**Examples:**

```
my_token,buy,EURUSD,lot=0.10,sl=1.0850,tp=1.0950
my_token,sell,GBPUSD,lot=0.05,sl_pips=50,tp_pips=100
my_token,buy,XAUUSD,lot=0.5,tp1=10@50%,tp2=20@30%,tp3=30@20%
my_token,closeall
my_token,closebuy,EURUSD
```

### TradingView Alert Message Examples

**For JSON Endpoint:**
```
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0850,
  "tp": 1.0950
}
```

**For Plain Text Endpoint:**
```
my_secret_token,buy,EURUSD,lot=0.10,sl=1.0850,tp=1.0950
```

---

## Dashboard Features

### Real-Time Monitoring

**Status Indicators**
- System health (OK/DRY RUN/ERROR)
- Trade Engine connection status
- MT5 bridge connection status
- ZMQ connectivity

**Trade Table**
- Symbol, Action, Volume
- Entry Price & Time
- Current P&L
- Trade Status (Open/Partial/Closed)
- Partial close details

**Analytics Cards**
- Total Trades Today
- Win Rate
- Daily PnL
- Max Drawdown

### Theme Toggle

- **Light Theme**: Clean white background, blue accents
- **Dark Theme**: Deep background, bright blue accents
- **Persistent**: Saved in browser localStorage

### Time-Based Updates

- **Status**: Updates every 2 seconds
- **Trade List**: Updates every 3 seconds
- **Analytics**: Updates every 5 seconds

---

## Performance Metrics

### PnL Metrics

| Metric | Description |
|--------|-------------|
| `total_pnl` | Gross profit/loss before commission |
| `total_commission` | Trading commission paid |
| `net_pnl` | Profit/loss after commission |
| `daily_pnl` | Daily cumulative P&L |

### Win Rate Metrics

| Metric | Description |
|--------|-------------|
| `total_trades` | Total number of closed trades |
| `wins` | Number of winning trades |
| `losses` | Number of losing trades |
| `win_rate` | Percentage of winning trades (0-100) |
| `avg_win` | Average profit per winning trade |
| `avg_loss` | Average loss per losing trade |
| `profit_factor` | (Total Wins) / (Total Losses) |
| `expectancy` | Average profit per trade |

### Drawdown Metrics

| Metric | Description |
|--------|-------------|
| `max_drawdown` | Largest peak-to-trough loss in currency |
| `max_drawdown_pct` | Max drawdown as percentage of peak |
| `current_drawdown` | Current drawdown from peak |
| `peak_equity` | Highest equity reached |
| `current_equity` | Current account equity |

### Calculation Formulas

```
Profit Factor = Sum(Wins) / Abs(Sum(Losses))
Expectancy = Net PnL / Total Trades
Max Drawdown % = (Peak Equity - Lowest Equity) / Peak Equity × 100
```

---

## Advanced Configuration

### Environment Variables (.env)

```bash
# Server
HOST=0.0.0.0
PORT=8003
RELOAD=true

# Database
DATABASE_URL=sqlite:///./trades.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:pass@localhost/pineconnector

# MT5 Bridge
MT5_ACCOUNT=123456789
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo

# Risk Management
DRY_RUN=false
MAX_TRADES_PER_DAY=20
MAX_DRAWDOWN_PERCENT=10.0

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# ZMQ Ports
ZMQ_SIGNAL_PORT=5555
ZMQ_COMMAND_PORT=5556
ZMQ_RESULT_PORT=5557
ZMQ_STATE_PORT=5558

# Auth
WEBHOOK_TOKEN=your_secret_token
```

### Running Modes

**Development (Hot Reload)**
```bash
python run.py --reload
```

**Production (No Reload)**
```bash
python run.py
```

**Dry Run / Paper Trading**
```bash
python run.py --dry-run
```

**Custom Port**
```bash
python run.py --port 9000
```

### Database Backends

**SQLite (Development)**
- Default, file-based, no setup needed
- Perfect for testing
- Database file: `./trades.db`

**PostgreSQL (Production)**
- Scalable, networked
- Better performance
- Connection string: `postgresql://user:password@host:port/database`

### MT5 Bridge Modes

**Mode 1: Python MetaTrader5 Package**
- Direct DLL integration
- Lower latency
- Requires Windows + MT5 installed
- Configure in `.env`

**Mode 2: MQL5 Expert Advisor**
- Network-based via ZMQ
- Works remotely
- More flexible deployment
- Requires EA running in MT5

---

## Best Practices

### Signal Design

1. **Use Shorthand for Simple TP**: `tp1=10@50%` instead of full JSON
2. **Always Specify SL**: Risk management requires defined stop loss
3. **Comment Your Signals**: Use `comment` field to identify strategy
4. **Magic Numbers**: Use consistent magic per strategy

### Risk Management

1. **Start Conservative**: Begin with low `max_trades_per_day`
2. **Test in Dry-Run**: Always test signals in paper trading first
3. **Monitor Drawdown**: Keep max_drawdown_percent at 10% or less
4. **Set Daily Limits**: Use `daily_loss_limit` to protect capital

### Partial TPs

1. **TP1 as Profit-Taking**: Close 30-50% at first target
2. **Breakeven Protection**: Enable `move_sl_to_be_on_tp1` for safety
3. **TP3 Scaling**: Reserve final portion for trend continuation

### Trailing Stops

1. **Activation**: Set 20+ pips to avoid early exits
2. **Distance**: Keep 10+ pips to avoid getting stopped out by noise
3. **Step Size**: 1-5 pips for stable updates

---

## Common Scenarios

### Scalping Strategy (Short Duration Trades)

```
buy,EURUSD,lot=0.5,sl=1.0880,tp=1.0920,time_exit_minutes=15
```
- Quick entry/exit
- 40 pips target
- 20 pips SL
- Auto-close after 15 minutes

### Swing Trade (Multi-Day, Breakeven Protection)

```json
{
  "action": "buy",
  "symbol": "EURUSD",
  "lot": 0.10,
  "sl": 1.0800,
  "tp": 1.1000,
  "partial_tp": {
    "tp1_pips": 50,
    "tp1_percent": 30,
    "tp2_pips": 100,
    "tp2_percent": 70,
    "move_sl_to_be_on_tp1": true
  }
}
```
- Close 30% at first target
- Move SL to breakeven
- Close 70% at second target

### Momentum Trade (Trailing Stop)

```json
{
  "action": "buy",
  "symbol": "XAUUSD",
  "lot": 0.5,
  "sl": 1900,
  "tp": 2000,
  "trailing": {
    "enabled": true,
    "activation_pips": 30,
    "distance_pips": 15,
    "step_pips": 5
  }
}
```
- Let trend run with trailing stop
- Activate after 30 pips profit
- Lock in profits every 15 pips

---

## Support & Documentation

- **Full API Reference**: See `08_API_REFERENCE.md`
- **Architecture Guide**: See `01_ARCHITECTURE.md`
- **Setup Instructions**: See `02_SETUP_GUIDE.md`
- **Risk Management**: See `09_RISK_MANAGEMENT_GUIDE.md`
- **Troubleshooting**: See `11_TROUBLESHOOTING_FAQ.md`
