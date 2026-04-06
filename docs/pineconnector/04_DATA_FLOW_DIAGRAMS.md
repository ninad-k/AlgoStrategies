# PineConnector Data Flow Diagrams

## 1. Signal Lifecycle (End-to-End)

```
                                    SIGNAL LIFECYCLE
  ═══════════════════════════════════════════════════════════════════════

  TradingView                Python Server              Rust Engine              MT5 Bridge              MT5 Terminal
  ───────────                ─────────────              ───────────              ──────────              ────────────
       │                          │                          │                       │                       │
       │  POST /webhook           │                          │                       │                       │
       │─────────────────────────>│                          │                       │                       │
       │                          │                          │                       │                       │
       │                     ┌────┴────┐                     │                       │                       │
       │                     │ Parse   │                     │                       │                       │
       │                     │ Alert   │                     │                       │                       │
       │                     └────┬────┘                     │                       │                       │
       │                          │                          │                       │                       │
       │                     ┌────┴────┐                     │                       │                       │
       │                     │  Auth   │                     │                       │                       │
       │                     │ Check   │──── FAIL ──> 401    │                       │                       │
       │                     └────┬────┘                     │                       │                       │
       │                          │ PASS                     │                       │                       │
       │                     ┌────┴────┐                     │                       │                       │
       │                     │  Risk   │                     │                       │                       │
       │                     │ Check   │──── FAIL ──> {"status":"rejected"}          │                       │
       │                     └────┬────┘                     │                       │                       │
       │                          │ PASS                     │                       │                       │
       │                     ┌────┴────┐                     │                       │                       │
       │                     │  Map    │                     │                       │                       │
       │                     │ Symbol  │                     │                       │                       │
       │                     └────┬────┘                     │                       │                       │
       │                          │                          │                       │                       │
       │  {"status":"accepted"}   │  ZMQ PUSH (:5555)        │                       │                       │
       │<─────────────────────────│─────────────────────────>│                       │                       │
       │                          │                          │                       │                       │
       │                          │                     ┌────┴────┐                  │                       │
       │                          │                     │ Create  │                  │                       │
       │                          │                     │ Managed │                  │                       │
       │                          │                     │Position │                  │                       │
       │                          │                     └────┬────┘                  │                       │
       │                          │                          │                       │                       │
       │                          │                          │  ZMQ PUSH (:5556)     │                       │
       │                          │                          │  ExecutionCommand     │                       │
       │                          │                          │──────────────────────>│                       │
       │                          │                          │                       │                       │
       │                          │                          │                  ┌────┴────┐                  │
       │                          │                          │                  │ Execute │                  │
       │                          │                          │                  │  Order  │                  │
       │                          │                          │                  └────┬────┘                  │
       │                          │                          │                       │                       │
       │                          │                          │                       │  order_send()         │
       │                          │                          │                       │─────────────────────> │
       │                          │                          │                       │                       │
       │                          │                          │                       │  result (ticket,      │
       │                          │                          │                       │  price, volume)       │
       │                          │                          │                       │<───────────────────── │
       │                          │                          │                       │                       │
       │                          │  ZMQ PUSH (:5557)        │  ZMQ PUSH (:5559)     │                       │
       │                          │  ExecutionResult         │  ExecutionResult       │                       │
       │                          │<─────────────────────────│<──────────────────────│                       │
       │                          │                          │                       │                       │
       │                     ┌────┴────┐                ┌────┴────┐                  │                       │
       │                     │ Update  │                │Activate │                  │                       │
       │                     │   DB    │                │Position │                  │                       │
       │                     │ Notify  │                │  State  │                  │                       │
       │                     └─────────┘                └─────────┘                  │                       │
```

---

## 2. Partial Take-Profit Flow

```
                           PARTIAL TP STATE MACHINE
  ═══════════════════════════════════════════════════════════════════

  State: WaitingTP1
       │
       │  Price reaches entry + tp1_pips
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  1. Calculate close lot = original_lot * tp1_percent / 100  │
  │  2. Send close_order (partial) to MT5 bridge                │
  │  3. If move_sl_to_be_on_tp1: send modify_order (SL=entry)  │
  │  4. Publish state update to Python (Telegram notification)  │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
  State: TP1Hit → WaitingTP2
       │
       │  Price reaches entry + tp2_pips
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  1. Calculate close lot = original_lot * tp2_percent / 100  │
  │  2. Send close_order (partial) to MT5 bridge                │
  │  3. If trail_after_tp2: activate trailing stop              │
  │  4. Publish state update                                    │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
  State: TP2Hit → WaitingTP3
       │
       │  Price reaches entry + tp3_pips
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  1. Close ALL remaining lot                                 │
  │  2. Publish state update (position complete)                │
  │  3. Remove position from managed positions                  │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
  State: Complete


  EXAMPLE with 0.30 lots, TP1=10@50%, TP2=20@30%, TP3=40@20%
  ──────────────────────────────────────────────────────────────
  Entry:  0.30 lots at 1.10000

  TP1 hit (1.10100):
    Close 0.15 lots (50%)  → 0.15 remaining
    SL moves to 1.10000 (breakeven)

  TP2 hit (1.10200):
    Close 0.09 lots (30%)  → 0.06 remaining
    Trailing activates (15 pip distance)

  TP3 hit (1.10400):
    Close 0.06 lots (100%) → 0.00 remaining
    Position complete
```

---

## 3. Trailing Stop Flow

```
                          TRAILING STOP LOGIC
  ═══════════════════════════════════════════════════════════

  Every 100ms tick:
       │
       ▼
  ┌─────────────┐     No
  │ Trailing    │─────────────> (skip)
  │ configured? │
  └──────┬──────┘
         │ Yes
         ▼
  ┌─────────────┐     No
  │  Active?    │──────┐
  │             │      │
  └──────┬──────┘      │
         │ Yes         ▼
         │      ┌─────────────┐     No
         │      │ Profit >=   │──────────> (skip, not activated yet)
         │      │ activation? │
         │      └──────┬──────┘
         │             │ Yes
         │             ▼
         │      ┌─────────────┐
         │      │ Activate    │
         │      │ trailing    │
         │      └──────┬──────┘
         │             │
         ▼             ▼
  ┌──────────────────────────┐
  │ Calculate new SL:        │
  │  LONG:  price - distance │
  │  SHORT: price + distance │
  └────────────┬─────────────┘
               │
               ▼
  ┌─────────────┐     No
  │ New SL more │──────────> (skip, don't move SL backward)
  │ favorable?  │
  └──────┬──────┘
         │ Yes
         ▼
  ┌─────────────┐     No
  │ Move >= step│──────────> (skip, prevent micro-updates)
  │   pips?     │
  └──────┬──────┘
         │ Yes
         ▼
  ┌─────────────────────┐
  │ Send modify_order   │
  │ to MT5 bridge       │
  │ Update position SL  │
  └─────────────────────┘


  EXAMPLE: BUY XAUUSD at 2300, trail activation=30 pips, distance=15, step=5
  ──────────────────────────────────────────────────────────────────────────
  Price 2310 (+10 pips): Not activated yet
  Price 2330 (+30 pips): ACTIVATED, SL = 2330 - 15 = 2315.00
  Price 2335 (+35 pips): Move = 5 pips >= step, SL = 2335 - 15 = 2320.00
  Price 2337 (+37 pips): Move = 2 pips < step=5, SKIP (no micro-update)
  Price 2340 (+40 pips): Move = 5 pips >= step, SL = 2340 - 15 = 2325.00
  Price 2335 (retrace) : New SL=2320 < current=2325, SKIP (don't move back)
  Price hits SL 2325   : Position closed by broker at 2325 (+25 pips)
```

---

## 4. Risk Check Pipeline

```
                          RISK CHECK PIPELINE
  ═══════════════════════════════════════════════════════════

  Incoming Signal
       │
       ▼
  ┌──────────────────┐
  │ Is close/cancel  │──── Yes ──> PASS (close commands bypass risk)
  │   action?        │
  └────────┬─────────┘
           │ No
           ▼
  ┌──────────────────┐
  │ 1. Dedup check   │──── FAIL ──> "Duplicate signal within 5s"
  │    (hash ring)   │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 2. Max lot size  │──── FAIL ──> "Lot 2.0 exceeds max 1.0"
  │    (config cap)  │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 3. Daily trades  │──── FAIL ──> "Daily trade limit reached (20)"
  │    (counter)     │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 4. Open/symbol   │──── FAIL ──> "Max open trades for EURUSD (3)"
  │    (per-symbol)  │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 5. Total open    │──── FAIL ──> "Max total open trades (10)"
  │    (global cap)  │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 6. Cooldown      │──── FAIL ──> "Cooldown: 3.2s remaining for EURUSD"
  │    (per-symbol)  │
  └────────┬─────────┘
           │ PASS
           ▼
  ┌──────────────────┐
  │ 7. Equity guard  │──── FAIL ──> "Daily loss limit $500 reached"
  │    (USD + %)     │
  └────────┬─────────┘
           │ PASS
           ▼
       APPROVED
  (increment counters, record trade time)
```

---

## 5. Webhook Request-Response Flow

```
                         WEBHOOK PROCESSING (< 50ms)
  ═══════════════════════════════════════════════════════════

  Client                          FastAPI                          Background
  ──────                          ───────                          ──────────
    │                                │                                 │
    │  POST /webhook                 │                                 │
    │  Body: JSON alert              │                                 │
    │  Header: X-Auth-Token          │                                 │
    │───────────────────────────────>│                                 │
    │                                │                                 │
    │                           [0-2ms] Read body                      │
    │                           [0-2ms] Parse JSON/text                │
    │                           [0-1ms] Authenticate                   │
    │                           [0-3ms] Risk check (in-memory)         │
    │                           [0-1ms] ZMQ PUSH (non-blocking)        │
    │                                │                                 │
    │  200 OK                        │                                 │
    │  {"status":"accepted",         │                                 │
    │   "signal_id":"a1b2..."}       │                                 │
    │<───────────────────────────────│                                 │
    │                                │                                 │
    │                                │──── async task ────────────────>│
    │                                │     DB write (save_signal)      │
    │                                │                                 │
    │  Total: 5-15ms typical         │                                 │
```

---

## 6. MT5 Bridge Reconnection Flow

```
                      MT5 RECONNECTION STRATEGY
  ═══════════════════════════════════════════════════════

  ┌──────────────┐
  │ MT5 Connected│
  │ (normal)     │
  └──────┬───────┘
         │
         │ Connection lost / API error
         ▼
  ┌──────────────┐
  │ Queue cmds   │ ← up to 50 commands buffered
  │ (30s timeout)│
  └──────┬───────┘
         │
         ▼ Attempt 1
  ┌──────────────┐      ┌─────────┐
  │ mt5.init()   │─ OK ─│Reconnect│
  │              │      │ Success │──> drain queue, resume
  └──────┬───────┘      └─────────┘
         │ FAIL
         │ wait 5s
         ▼ Attempt 2
  ┌──────────────┐
  │ mt5.init()   │─ OK ──> resume
  └──────┬───────┘
         │ FAIL
         │ wait 5s
         │ ... up to 10 attempts
         ▼
  ┌──────────────┐
  │  All retries │
  │  exhausted   │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────┐
  │ Send error results for   │
  │ all queued commands       │
  │ Log CRITICAL error       │
  │ Continue polling for     │
  │ reconnection             │
  └──────────────────────────┘
```

---

## 7. Database Write Flow

```
                        DB WRITES (Non-Blocking)
  ═══════════════════════════════════════════════════════

  Webhook Handler                Background Task               SQLite
  ───────────────                ───────────────               ──────
       │                              │                          │
       │  run_in_executor(            │                          │
       │    save_signal)              │                          │
       │─────────────────────────────>│                          │
       │                              │  INSERT INTO signals     │
       │  (returns immediately,       │─────────────────────────>│
       │   does not wait)             │                          │
       │                              │                          │
       │                              │                          │
  Result Consumer                     │                          │
  ───────────────                     │                          │
       │                              │                          │
       │  Execution result arrives    │                          │
       │  via ZMQ (:5557)             │                          │
       │                              │                          │
       │  run_in_executor(            │                          │
       │    update_trade)             │                          │
       │─────────────────────────────>│                          │
       │                              │  UPDATE trades           │
       │                              │  SET ticket=X,           │
       │                              │      entry_price=Y,      │
       │                              │      status='open'       │
       │                              │─────────────────────────>│
       │                              │                          │

  KEY PRINCIPLE: DB writes NEVER block the webhook response or
  the ZMQ signal dispatch. They run in executor threads.
```
