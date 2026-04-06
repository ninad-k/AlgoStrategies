# PineConnector Troubleshooting & FAQ

## Common Issues

### 1. "Invalid token" (HTTP 401)

**Cause**: Webhook token doesn't match.

**Fix**:
- Check `WEBHOOK_TOKEN` in `.env` matches what you send
- Ensure no trailing whitespace in `.env`
- Token can be sent via header, query param, or body — check which you're using

```bash
# Test with header
curl -X POST http://localhost:8003/webhook -H "X-Auth-Token: your_token" ...

# Test with query param
curl -X POST "http://localhost:8003/webhook?token=your_token" ...
```

### 2. "Parse error" (HTTP 400)

**Cause**: Alert body is malformed.

**Fix**:
- Ensure JSON is valid (no trailing commas, proper quotes)
- `action` must be a valid value: `buy`, `sell`, `closebuy`, etc.
- `lot` must be >= 0.01
- Check TradingView placeholder syntax: `{{strategy.order.action}}` not `{strategy.order.action}`

### 3. Signal "accepted" but no trade appears in MT5

**Possible causes**:

a) **Trade engine not running**:
```bash
# Check health
curl http://localhost:8003/api/health
# Look at "trade_engine" field
```

b) **MT5 bridge not connected**:
- Check MT5 terminal is running
- Check credentials in `.env`
- Check health endpoint: `mt5_connected: false`

c) **Dry-run mode active**:
- Check: `curl http://localhost:8003/api/health` → `dry_run: true`
- Remove `DRY_RUN=true` from `.env` or restart without `--dry-run`

d) **Symbol mapping mismatch**:
- Your TradingView symbol doesn't match MT5 broker symbol
- Edit `configs/symbols.yaml` to add mapping

### 4. "Daily trade limit reached"

**Cause**: You've hit `max_trades_per_day` in `configs/risk.yaml`.

**Fix**:
- Increase the limit in `configs/risk.yaml`
- Wait for daily reset (configured UTC hour)
- Close commands still work (they bypass risk checks)

### 5. "Cooldown: Xs remaining for SYMBOL"

**Cause**: Multiple signals for the same symbol within `cooldown_seconds`.

**Fix**:
- Reduce `cooldown_seconds` in `configs/risk.yaml`
- Or ensure your TradingView alerts fire less frequently

### 6. Partial TP not triggering

**Possible causes**:

a) **TP pips set to 0**: Check that `tp1_pips`, `tp2_pips`, `tp3_pips` are all > 0

b) **Price not reaching TP level**: The Trade engine checks prices on a 100ms tick interval using the last known price from execution results. If no new results come in, the engine won't detect price changes.

c) **Lot too small**: If computed close lot < broker minimum (0.01), the engine closes all remaining instead of partial.

### 7. Trailing stop not moving

**Possible causes**:

a) **Not activated**: Price hasn't reached `activation_pips` threshold yet

b) **Step too large**: `step_pips` is larger than the price movement since last update

c) **Moving in wrong direction**: SL only moves in the favorable direction — never backward

### 8. ZMQ connection errors

```
ZMQ send error: Resource temporarily unavailable
```

**Fix**:
- Ensure Trade engine is running BEFORE Python server
- Check no other process is using ports 5555-5559
- Restart both services

### 9. MT5 "Trade disabled" error

**Cause**: MT5 terminal doesn't allow automated trading.

**Fix**:
1. In MT5: Tools → Options → Expert Advisors
2. Check "Allow algorithmic trading"
3. Click the "AutoTrading" button in MT5 toolbar (should be green)

### 10. Trade engine won't compile

```
error: failed to run custom build command for `zmq-sys`
```

**Fix**: Install libzmq system library:
```powershell
# Windows (vcpkg)
vcpkg install zeromq:x64-windows
set LIBZMQ_LIB_DIR=C:\vcpkg\installed\x64-windows\lib
set LIBZMQ_INCLUDE_DIR=C:\vcpkg\installed\x64-windows\include
cargo build --release
```

---

## FAQ

### Q: Can I run this on Linux/Mac?

**A**: The Python webhook server and Trade engine work on any OS. However, the MetaTrader5 Python package only works on Windows. For Linux, use the MQL5 EA bridge mode (`MT5_BRIDGE_MODE=mql5`) with MT5 running on a Windows machine or Wine.

### Q: How many alerts can it handle per second?

**A**: The webhook server can handle 100+ requests/second. The bottleneck is MT5 order execution (50-500ms per order). With the queue design, alerts are accepted instantly and executed in order.

### Q: Can I run multiple MT5 accounts?

**A**: Yes. Run multiple instances of the MT5 bridge, each connected to a different MT5 terminal on different ZMQ ports. Route signals by `magic` number.

### Q: Does it work with MT4?

**A**: Not directly. The Python MetaTrader5 package only supports MT5. For MT4, use the MQL5 EA bridge pattern adapted for MQL4, or use a third-party MT4 API bridge.

### Q: Can I use this with crypto exchanges instead of MT5?

**A**: Yes. Replace the MT5 bridge with an exchange API bridge (e.g., Binance, Bybit). The Python webhook, Trade engine, and all risk management remain identical. Only the bridge module needs to change.

### Q: What happens if TradingView sends the same alert twice?

**A**: The dedup check (Check 1 in risk engine) catches duplicate signals within the configured window (default 5s). The second signal is rejected with "Duplicate signal within 5s".

### Q: What if the VPS reboots?

**A**: If configured as Windows services (NSSM), all components restart automatically. The Trade engine starts fresh with no managed positions. On startup, the system should reconcile with MT5 to detect any positions opened before the restart.

### Q: Can I test without risking real money?

**A**: Yes, two options:
1. **Dry-run mode**: `py -3 run.py --dry-run` — processes everything but skips MT5 execution
2. **Demo account**: Connect to your broker's demo MT5 server

### Q: How do I see all rejected signals?

**A**: Query the database:
```bash
sqlite3 data/pineconnector.db "SELECT * FROM signals WHERE risk_passed = 0 ORDER BY created_at DESC LIMIT 20"
```

### Q: Can I change risk settings without restarting?

**A**: Currently, risk config loads on startup. To change settings:
1. Edit `configs/risk.yaml`
2. Restart the Python server (Trade engine doesn't need restart)

### Q: What happens during market close?

**A**: Pending orders stay in MT5. The Trade engine continues monitoring positions (trailing stops, time exits). Market orders will fail with broker errors during closed hours — the system handles this gracefully.

---

## Diagnostic Commands

```bash
# System health
curl http://localhost:8003/api/health

# Recent trades
curl http://localhost:8003/api/trades?limit=10

# Open positions
curl http://localhost:8003/api/trades/open

# Analytics
curl "http://localhost:8003/api/analytics?days=7"

# Config (no secrets)
curl http://localhost:8003/api/config

# Test webhook (dry-run safe)
curl -X POST http://localhost:8003/webhook \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: your_token" \
  -d '{"action":"buy","symbol":"EURUSD","lot":0.01,"sl":30,"tp":60}'

# Check SQLite database directly
sqlite3 data/pineconnector.db ".tables"
sqlite3 data/pineconnector.db "SELECT COUNT(*) FROM signals"
sqlite3 data/pineconnector.db "SELECT COUNT(*) FROM trades WHERE status='open'"
```
