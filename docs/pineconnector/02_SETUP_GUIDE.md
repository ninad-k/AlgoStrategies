# PineConnector Setup Guide

## Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Windows 10/11 | 64-bit | MT5 requires Windows |
| Python | 3.10+ | 3.11 recommended |
| Rust | 1.70+ | Latest stable |
| MetaTrader 5 | Latest | Must be running |
| libzmq | 4.3+ | ZeroMQ C library |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/ninad-k/AlgoStrategies.git
cd AlgoStrategies/tools/pineconnector
```

---

## Step 2: Python Setup

### Install dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt includes:**
- `fastapi` + `uvicorn` — web server
- `pyzmq` — ZeroMQ bindings
- `pydantic` — data validation
- `PyYAML` — config parsing
- `aiohttp` — async HTTP (Telegram)
- `MetaTrader5` — MT5 API (Windows only)
- `asyncpg` — PostgreSQL (optional)
- `python-dotenv` — environment config

### Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# REQUIRED: Webhook authentication
WEBHOOK_TOKEN=your_unique_secret_token_here

# MT5 connection (for Python bridge mode)
MT5_BRIDGE_MODE=python
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=YourBroker-Server
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# Optional: Telegram notifications
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-1001234567890

# Optional: Database
DB_BACKEND=sqlite

# Optional: Start in paper mode
DRY_RUN=false
```

### Generate a secure webhook token

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Step 3: Rust Setup

### Install Rust toolchain

```bash
# If not already installed:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Install libzmq (Windows)

**Option A — vcpkg:**
```bash
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg && bootstrap-vcpkg.bat
vcpkg install zeromq:x64-windows
set LIBZMQ_LIB_DIR=C:\path\to\vcpkg\installed\x64-windows\lib
set LIBZMQ_INCLUDE_DIR=C:\path\to\vcpkg\installed\x64-windows\include
```

**Option B — Pre-built binary:**
1. Download from https://zeromq.org/download/
2. Extract to `C:\libzmq`
3. Set environment variables:
```bash
set LIBZMQ_LIB_DIR=C:\libzmq\lib
set LIBZMQ_INCLUDE_DIR=C:\libzmq\include
```

### Build the engine

```bash
cd tools/pineconnector/rust
cargo build --release
```

The binary will be at `target/release/pineconnector-engine.exe`

---

## Step 4: MT5 Bridge Setup

### Option A: Python Bridge (recommended)

No additional setup needed. The Python `MetaTrader5` package connects directly.

**Requirements:**
- MetaTrader 5 terminal must be running
- "Allow algorithmic trading" must be enabled in MT5 settings
- Login credentials set in `.env`

### Option B: MQL5 ZMQ EA

1. **Install mql-zmq library:**
   - Download from https://github.com/dingmaotu/mql-zmq
   - Copy `Include/Zmq/` to your MT5 `MQL5/Include/` folder
   - Copy the required DLLs to MT5 `MQL5/Libraries/`

2. **Install the EA:**
   - Copy `mql5/PineConnector_EA.mq5` to `MQL5/Experts/`
   - Compile in MetaEditor (press F7)

3. **Attach to chart:**
   - Open any chart in MT5
   - Drag `PineConnector_EA` onto the chart
   - Enable "Allow DLL imports" in EA settings
   - Set ZMQ addresses (default ports should work)

4. **Update `.env`:**
   ```
   MT5_BRIDGE_MODE=mql5
   ```

---

## Step 5: Configure Risk Management

Edit `configs/risk.yaml`:

```yaml
max_lot_size: 1.0           # Maximum lot per trade
max_trades_per_day: 20      # Daily trade cap
max_open_per_symbol: 3      # Max concurrent per symbol
max_total_open: 10          # Max total open positions
cooldown_seconds: 5         # Min seconds between trades/symbol
max_daily_loss_usd: 500.0   # Daily loss cap in USD
max_daily_loss_percent: 5.0 # Daily loss cap as % of equity
max_spread_points: 30       # Max spread allowed
dedup_window_seconds: 5     # Duplicate signal window
```

---

## Step 6: Configure Symbol Mapping

Edit `configs/symbols.yaml` to match your broker's symbol names:

```yaml
mapping:
  XAUUSD: XAUUSD       # Some brokers use GOLD or XAUUSDm
  EURUSD: EURUSD       # Some brokers use EURUSDm
  NAS100: USTEC        # Broker-specific name
  US30: US30.cash      # Broker-specific name

pip_sizes:
  default: 0.0001
  XAUUSD: 0.01
  USDJPY: 0.01
  NAS100: 0.1
```

---

## Step 7: Verify Setup

### Start in dry-run mode first

```bash
# Terminal 1
cd tools/pineconnector
py -3 run.py --dry-run

# Terminal 2
cd tools/pineconnector/rust
cargo run --release
```

### Test with curl

```bash
curl -X POST http://localhost:8003/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-Auth-Token: your_unique_secret_token_here" ^
  -d "{\"action\":\"buy\",\"symbol\":\"EURUSD\",\"lot\":0.01,\"sl\":30,\"tp\":60}"
```

Expected response:
```json
{"status":"accepted","signal_id":"a1b2c3d4e5f6g7h8","reason":""}
```

### Check health

```bash
curl http://localhost:8003/api/health
```

### Open dashboard

Navigate to `http://localhost:8003/` in your browser.

---

## Step 8: Configure TradingView

1. Go to TradingView chart with your strategy
2. Create Alert → Notifications tab → Enable "Webhook URL"
3. Set URL: `http://YOUR_VPS_IP:8003/webhook`
4. Set alert message (see User Guide for formats)
5. Save alert

---

## Telegram Bot Setup (Optional)

1. Message `@BotFather` on Telegram
2. Send `/newbot`, follow prompts
3. Copy the bot token to `.env` as `TELEGRAM_BOT_TOKEN`
4. Create a group/channel, add your bot
5. Get chat ID: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Set `TELEGRAM_CHAT_ID` in `.env`

---

## PostgreSQL Setup (Optional)

```bash
# Install PostgreSQL
# Create database:
createdb pineconnector

# Update .env:
DB_BACKEND=postgresql
PG_DSN=postgresql://user:password@localhost:5432/pineconnector
```

Note: The app auto-creates tables on first startup.

---

## Quick Verification Checklist

- [ ] Python dependencies installed (`pip list | findstr fastapi`)
- [ ] Rust binary builds (`cargo build --release`)
- [ ] `.env` configured with webhook token
- [ ] MT5 terminal running with algo trading enabled
- [ ] Dry-run test succeeds (curl returns `accepted`)
- [ ] Dashboard loads at `http://localhost:8003/`
- [ ] Health endpoint shows all green
- [ ] TradingView webhook URL configured
