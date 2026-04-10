# AlgoStrategies - Data Flow Diagrams

## 1. Signal Generation & Order Execution Flow

This is the primary trading pipeline: from signal to order.

```
+==========================================+
|   SIGNAL SOURCES                         |
+==========================================+
|                                          |
|  TradingView          MetaTrader 5       |
|  +----------------+   +--------------+   |
|  | Pine Strategy  |   | MQL5 EA      |   |
|  | generates      |   | generates    |   |
|  | alert on       |   | signal from  |   |
|  | bar close      |   | tick/bar     |   |
|  +-------+--------+   +------+-------+   |
|          |                    |           |
+====+=====+===========+===+===+===========+
     |                     |
     | JSON webhook        | Direct order
     | POST request        | via Trade.mqh
     v                     v
+----+-----+         +----+----------+
| ReyConnector|       | MT5 Terminal   |
| Webhook     |       | Order Manager  |
| Ingest      |       | (built-in)     |
| :5242       |       +----+----------+
+----+--------+            |
     |                     |
     | Forward alert       |
     v                     |
+----+--------+            |
| ReyConnector|            |
| Control API |            |
| :5241       |            |
+----+--------+            |
     |                     |
     | Signal log          |
     | (in-memory)         |
     v                     |
+----+---------+           |
| Execution    |           |
| Engine       |           |
| (Protocol)   |           |
+----+---------+           |
     |                     |
     | BrokerCommand       |
     v                     v
+----+---------------------+----+
|      BROKER / MT5 SERVER      |
|   (Order placed on market)    |
+-------------------------------+
```

### Webhook Alert Format (TradingView -> ReyConnector)

```
POST /v1/webhook?connection_id=conn-demo-001

Body (raw text):
  "demo,buy,EURUSD"

                    |
                    v

IncomingAlertEnvelope (Pydantic):
  {
    "id": "uuid-...",
    "connectionId": "conn-demo-001",
    "rawBody": "demo,buy,EURUSD",
    "idempotencyKey": "...",
    "receivedAtUtc": "2026-04-09T12:00:00Z"
  }
```

---

## 2. Trade Attribution & P&L Flow

After trades execute, this pipeline categorizes, attributes, and reports.

```
+-------------------------------+
|   MT5 Terminal                |
|   (Completed trades in       |
|    deal history)             |
+-------------+-----------------+
              |
              | Export via TradeSegregatorEA
              v
+-------------+-----------------+
|  Trade Segregator EA (MQL5)  |
|                               |
|  Reads: rules-for-ea.csv    |
|  Scans: deal history          |
|  Computes: duration per deal |
|                               |
|  Outputs to MQL5/Files/:     |
|  - trade_segregator_deals.json|
|  - trade_segregator_deals.csv |
+-------------+-----------------+
              |
              | JSON file import
              v
+-------------+-----------------+
|  Trade Segregator Desktop    |
|  (.NET WPF Application)     |
|                               |
|  1. Import JSON deals        |
|  2. Load default-rules.json  |
|  3. Rule Engine evaluates:   |
|     - Top-to-bottom match    |
|     - First match wins       |
|     - Unmatched -> "uncategorized"
|  4. Manual Sort tab:         |
|     - User assigns category  |
|     - Override auto-results  |
|  5. Export categorized CSV   |
+-------------+-----------------+
              |
              | CSV upload (or API)
              v
+-------------+-----------------+
|  Trading Dashboard            |
|  (FastAPI + PostgreSQL)       |
|                               |
|  POST /api/v1/upload/trades  |
|       |                       |
|       v                       |
|  +---------------------------+|
|  | Parse CSV/Excel           ||
|  | Deduplicate by ticket     ||
|  | Store in trades table     ||
|  +------------+--------------+|
|               |               |
|               v               |
|  +---------------------------+|
|  | Attribution Engine        ||
|  | - Match by magic number   ||
|  | - Match by comment tag    ||
|  | - Assign: trader,         ||
|  |   strategy, guest         ||
|  | - Confidence score        ||
|  +------------+--------------+|
|               |               |
|               v               |
|  +---------------------------+|
|  | Risk Metrics Calculator   ||
|  | - Daily P&L               ||
|  | - Drawdown                ||
|  | - VaR (95%)               ||
|  | - Sharpe Ratio            ||
|  +------------+--------------+|
|               |               |
|               v               |
|  +---------------------------+|
|  | API Endpoints             ||
|  | GET /pnl/{account_id}    ||
|  | GET /traders              ||
|  | GET /strategies           ||
|  +---------------------------+|
|               |               |
|               v               |
|  +---------------------------+|
|  | Frontend Dashboard        ||
|  | - Account rollup view     ||
|  | - Strategy performance    ||
|  | - Trader leaderboard      ||
|  | - Risk limit alerts       ||
|  +---------------------------+|
+-------------------------------+
```

### Rule Engine Evaluation Flow (Trade Segregator)

```
Input: Deal { symbol: "EURUSD", duration: 45 min, profit: 12.50, magic: 100 }

  Rule 1: "scalping"  (duration < 15 AND profit between -5..5)
    -> duration=45 FAILS -> skip

  Rule 2: "intraday"  (duration >= 15 AND duration < 1440)
    -> duration=45 PASS, duration<1440 PASS -> MATCH!
    -> categoryId = "intraday"

  (Stop. First match wins.)
```

---

## 3. Market Sentiment Analysis Flow

```
+--------------------+
|  User / Frontend   |
|  GET /api/analysis |
|     /EURUSD        |
+--------+-----------+
         |
         v
+--------+-----------+
|  Cache Check       |
|  (5 min TTL)       |
|  Hit? -> Return    |
|  Miss? -> Continue |
+--------+-----------+
         |
         | Cache miss: fetch all data in parallel
         v
+--------+------+--------+--------+---------+
|               |        |        |         |
v               v        v        v         v
+----------+ +------+ +------+ +-------+ +--------+
| Price    | | OHLCV| | News | | Econ  | | Tech   |
| Current  | | 1Y   | | API  | | Cal.  | | Levels |
| (live)   | | Daily | | (4hr | | (12hr | | Compute|
|          | |      | | cache)| | cache)| |        |
+----+-----+ +--+---+ +--+---+ +---+---+ +---+----+
     |          |         |         |         |
     +----------+---------+---------+---------+
                          |
                          v
              +-----------+-----------+
              |  AI Analysis Engine   |
              |                       |
              |  Priority chain:      |
              |  1. Groq (fast/free)  |
              |  2. Anthropic Claude  |
              |  3. OpenAI GPT       |
              |  4. Neutral fallback  |
              |                       |
              |  Input: price, tech   |
              |  levels, news, events |
              |                       |
              |  Output:              |
              |  - direction          |
              |  - confidence         |
              |  - recommendation     |
              |  - key levels         |
              |  - news sentiment     |
              +-----------+-----------+
                          |
                          v
              +-----------+-----------+
              |  SymbolAnalysis       |
              |  (Pydantic model)     |
              |                       |
              |  -> Cache (5 min)     |
              |  -> Return to client  |
              +------------------------+
```

### Stock Scanner Background Flow

```
POST /api/scanner/start
         |
         v
+--------+---------+
|  Scanner Thread   |
|  (Background)    |
+--------+---------+
         |
         | For each symbol in universe (S&P 500 + watchlist)
         v
+--------+--+------+--------+
|           |      |        |
v           v      v        v
+-------+ +----+ +------+ +-------+
| Tech  | |Fund| | AI   | | Price |
| Score | |Score| |Score | | Data  |
| RSI,  | |P/E,| |Claude| |       |
| MACD, | |ROE,| |news +| |       |
| Trend | |D/E | |chart | |       |
+---+---+ +-+--+ +--+---+ +---+---+
    |        |       |         |
    +--------+-------+---------+
             |
             v
    +--------+---------+
    | Multi-Factor      |
    | Scoring           |
    |                   |
    | Categories:       |
    | - Multibagger(75+)|
    | - Investment (65+)|
    | - Swing Med  (60+)|
    | - Swing Short(60+)|
    +--------+----------+
             |
             v
    +--------+----------+
    | SQLite DB          |
    | stock_scores table |
    | scan_sessions table|
    +--------------------+
```

---

## 4. ML Model Training & Inference Flow

```
TRAINING PIPELINE
=================

+------------------+
| Yahoo Finance    |
| 1H OHLCV Data   |
| (2+ years)       |
+--------+---------+
         |
         v
+--------+---------+
| Feature Eng.     |
| (features.py)    |
|                   |
| Computes:        |
| - EMA (9,20,     |
|   50,200)        |
| - RSI (14)       |
| - ATR (14)       |
| - SuperTrend     |
|   (10, 3.0)      |
| - MACD           |
|   (12, 26, 9)    |
| - Bollinger      |
|   Bands          |
| - Volume Profile |
+--------+---------+
         |
         v
+--------+---------+
| Target Labeling  |
|                   |
| Label = 1 if     |
|  price rises 1%+ |
|  within next 4H  |
| Label = 0 else   |
+--------+---------+
         |
         v
+--------+---------+
| Time-Series      |
| Split            |
| (no lookahead)   |
+--------+---------+
         |
    +----+----+
    |         |
    v         v
+---+---+ +---+---+
| Train | | Valid |
| Set   | | Set   |
+---+---+ +---+---+
    |         |
    v         v
+---+---------+---+
| LightGBM        |
| Classifier      |
| Train + Eval    |
|                  |
| Metrics:         |
| - Accuracy       |
| - AUC-ROC        |
| - Classification |
|   Report         |
+--------+---------+
         |
         v
+--------+---------+
| Export ONNX      |
| saved_models/    |
| ema200_squeeze   |
|   .onnx          |
+------------------+


INFERENCE PIPELINE
==================

+------------------+     +------------------+
| Live OHLCV       |     | ONNX Model       |
| (current bar)    |     | (ema200_squeeze)  |
+--------+---------+     +--------+---------+
         |                         |
         v                         v
+--------+-------------------------+---------+
| Feature Engineering (same pipeline)        |
| -> Feature vector                          |
+--------+----------------------------------+
         |
         v
+--------+---------+
| ONNX Runtime     |
| predict()        |
|                   |
| Output:           |
| - probability     |
|   (0.0 - 1.0)    |
| - signal: bool    |
|   (threshold 0.5) |
+------------------+
```

---

## 5. Backtesting & Report Generation Flow

```
+---------------------+   +--------------------+   +-------------------+
| TradingView         |   | MT5 Strategy       |   | Python Backtester |
| Strategy Tester     |   | Tester             |   |                   |
+----------+----------+   +---------+----------+   +---------+---------+
           |                        |                        |
           v                        v                        v
+----------+----------+   +---------+----------+   +---------+---------+
| Export results       |   | Export HTML/CSV    |   | Generate results  |
| to CSV/JSON          |   | from MT5           |   | programmatically  |
+----------+----------+   +---------+----------+   +---------+---------+
           |                        |                        |
           v                        v                        v
+----------+------------------------+------------------------+----------+
|                    backtesting/results/<platform>/                     |
|   Naming: <STRATEGY>_<SYMBOL>_<TIMEFRAME>_<DATERANGE>.<ext>          |
+---------------------------------+-------------------------------------+
                                  |
                                  v
+---------------------------------+-------------------------------------+
|              scripts/build_strategy_report.py                         |
|                                                                       |
|  1. Read MT5 export (Deals, Orders, Results sheets)                  |
|  2. Parse trade entries & exits                                       |
|  3. Extract strategy tag from comment: "(combo)" -> "combo"          |
|  4. Group trades by strategy                                          |
|  5. Compute per-strategy metrics:                                     |
|     - Total trades, win rate, profit factor                          |
|     - Sharpe ratio, max drawdown, CAGR                               |
|     - Average trade duration                                          |
|  6. Output: strategy_analysis_N.xlsx                                  |
+---------------------------------+-------------------------------------+
                                  |
                                  v
+---------------------------------+-------------------------------------+
|                  backtesting/exports/                                  |
|                                                                       |
|  trades/         -> trade_id, entry, exit, P&L, duration, tags       |
|  equity_curves/  -> timestamp, equity, drawdown, daily_return        |
|  metrics/        -> metric/value pairs (sharpe, win_rate, etc.)      |
+-----------------------------------------------------------------------+
```

---

## 6. Configuration & Environment Data Flow

```
+-------------------+     +-------------------+     +------------------+
| .env.example      |     | broker_config     |     | symbols.yaml     |
|                   |     | .example.yaml     |     |                  |
| - TELEGRAM_TOKEN  |     |                   |     | - indian_equity  |
| - DISCORD_WEBHOOK |     | - zerodha         |     | - forex majors   |
| - WEBHOOK_SECRET  |     | - angel_one       |     | - crypto spot    |
| - DB_URL          |     | - fyers           |     | - us_equity      |
| - BINANCE_KEYS    |     | - interactive_    |     |                  |
| - NEWS_API_KEY    |     |   brokers         |     +--------+---------+
|                   |     | - alpaca          |              |
+--------+----------+     | - binance/bybit   |              |
         |                | - metatrader5     |              |
         |                +--------+----------+              |
         |                         |                         |
         v                         v                         v
+--------+-------------------------+-------------------------+--------+
|                      Application Runtime                            |
|                                                                      |
|  +------------------+     +------------------+     +-------------+  |
|  | Execution Layer  |<----|  configs/         |--->| MQL5 / Pine |  |
|  | (broker connect) |     |  timeframes.yaml  |    | (symbols)   |  |
|  +------------------+     +------------------+     +-------------+  |
|                                                                      |
|  +------------------+     +------------------+                      |
|  | Monitoring       |<----| .env             |                      |
|  | (notifications)  |     | (API keys)       |                      |
|  +------------------+     +------------------+                      |
+----------------------------------------------------------------------+
```

### Timeframe Mapping (configs/timeframes.yaml)

```
  Platform Mapping Example:
  +-----------+-------------+----------+-----------+
  | Label     | TradingView | MQL5     | Freqtrade |
  +-----------+-------------+----------+-----------+
  | 1m        | "1"         | PERIOD_M1| "1m"      |
  | 5m        | "5"         | PERIOD_M5| "5m"      |
  | 15m       | "15"        | PERIOD_M15| "15m"    |
  | 1h        | "60"        | PERIOD_H1| "1h"     |
  | 4h        | "240"       | PERIOD_H4| "4h"     |
  | 1D        | "D"         | PERIOD_D1| "1d"     |
  +-----------+-------------+----------+-----------+
```
