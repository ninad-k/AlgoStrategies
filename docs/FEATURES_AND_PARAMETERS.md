# AlgoStrategies - Feature & Parameter Reference

## Table of Contents

1. [MQL5 Expert Advisors](#1-mql5-expert-advisors)
2. [Pine Script Strategies](#2-pine-script-strategies)
3. [ReyConnector](#3-reyconnector)
4. [MT5 Trade Segregator](#4-mt5-trade-segregator)
5. [Market Sentiment Dashboard](#5-market-sentiment-dashboard)
6. [Stock Scanner](#6-stock-scanner)
7. [ML Models](#7-ml-models)
8. [Trading Dashboard](#8-trading-dashboard)
9. [Configuration Files](#9-configuration-files)
10. [Report Builder](#10-report-builder)

---

## 1. MQL5 Expert Advisors

### 1.1 FairValueGap_Regime_EA

**File**: `mql5/experts/FairValueGap_Regime_EA.mq5`
**Strategy**: Detects Fair Value Gaps (price imbalances) and enters on pullback into the gap, filtered by EMA regime and ADX strength.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `MinGapSize` | double | 10.0 | Minimum FVG size in points |
| `LookbackBars` | int | 50 | Bars to scan for FVGs |
| `MaxTrackedFVGs` | int | 5 | Maximum concurrent tracked gaps |
| `EMA_Period` | int | 200 | EMA period for regime filter |
| `EMA_Timeframe` | ENUM_TIMEFRAMES | PERIOD_H1 | Timeframe for EMA calculation |
| `UseADXFilter` | bool | true | Enable ADX directional filter |
| `ADX_Period` | int | 14 | ADX indicator period |
| `ADX_Threshold` | double | 20.0 | Minimum ADX for trend confirmation |
| `RiskPercent` | double | 1.0 | Risk per trade (% of equity) |
| `SL_ATR_Mult` | double | 1.5 | Stop loss as ATR multiple |
| `TP1_R` | double | 1.0 | Take profit 1 as R-multiple |
| `TP2_R` | double | 2.0 | Take profit 2 as R-multiple |
| `TP3_R` | double | 3.0 | Take profit 3 as R-multiple |
| `ClosePercent1` | double | 40.0 | % of position closed at TP1 |
| `ClosePercent2` | double | 30.0 | % of position closed at TP2 |
| `ClosePercent3` | double | 30.0 | % of position closed at TP3 |
| `SessionStart` | string | "00:00" | Trading session start (server time) |
| `SessionEnd` | string | "23:59" | Trading session end |
| `MaxSpread` | int | 30 | Maximum spread in points |
| `MaxDailyTrades` | int | 5 | Maximum trades per day |
| `MagicNumber` | int | 100001 | Unique EA identifier |

### 1.2 EMA200Squeeze_EA

**File**: `mql5/experts/EMA200Squeeze_EA.mq5`
**Strategy**: Identifies price compression near EMA 200 (squeeze), enters on breakout with multi-level profit booking.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `EMA_Length` | int | 200 | EMA period |
| `SqueezeThreshold` | double | 0.5 | Max distance from EMA (% of ATR) to qualify as squeeze |
| `BreakoutBars` | int | 3 | Consecutive bars outside squeeze to confirm breakout |
| `ATR_Period` | int | 14 | ATR period for volatility |
| `RiskPercent` | double | 1.0 | Risk per trade |
| `SL_Points` | int | 0 | Fixed SL in points (0 = use ATR) |
| `SL_ATR_Mult` | double | 2.0 | SL as ATR multiple |
| `TP1_Points` | int | 200 | Take profit 1 in points |
| `TP2_Points` | int | 400 | Take profit 2 in points |
| `TP3_Points` | int | 600 | Take profit 3 in points |
| `ClosePercent1` | double | 50.0 | Position % closed at TP1 |
| `ClosePercent2` | double | 30.0 | Position % closed at TP2 |
| `UseTrailing` | bool | true | Enable trailing stop |
| `TrailingStart` | int | 300 | Points in profit to activate trailing |
| `TrailingStep` | int | 50 | Trailing stop step size |
| `MagicNumber` | int | 100002 | Unique EA identifier |

### 1.3 SmartMoneyConcepts_EA

**File**: `mql5/experts/SmartMoneyConcepts_EA.mq5`
**Strategy**: Implements Smart Money structure detection: Break of Structure (BOS), Change of Character (CHoCH), Order Blocks, and Fair Value Gaps for institutional-style entries.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `StructureLookback` | int | 50 | Bars to analyze for swing highs/lows |
| `MinSwingSize` | double | 20.0 | Minimum swing size in points |
| `UseBOS` | bool | true | Trade Break of Structure signals |
| `UseCHoCH` | bool | true | Trade Change of Character signals |
| `UseOrderBlocks` | bool | true | Require Order Block for entry |
| `UseFVG` | bool | true | Require FVG for entry |
| `OB_MaxAge` | int | 20 | Max bars age for valid Order Block |
| `FVG_MinSize` | double | 5.0 | Minimum FVG size in points |
| `HTF_Timeframe` | ENUM_TIMEFRAMES | PERIOD_H4 | Higher timeframe for bias |
| `RiskPercent` | double | 1.0 | Risk per trade |
| `SL_Type` | int | 0 | 0=Below structure, 1=Fixed points |
| `SL_Buffer` | double | 5.0 | Extra SL buffer in points |
| `RR_Ratio` | double | 2.0 | Minimum risk-reward ratio |
| `MaxDailyTrades` | int | 3 | Maximum trades per day |
| `MaxSpread` | int | 25 | Maximum spread in points |
| `MagicNumber` | int | 100003 | Unique EA identifier |

### 1.4 EMATunnel_Breakout_EA

**File**: `mql5/experts/EMATunnel_Breakout_EA.mq5`
**Strategy**: Uses a tunnel of two EMAs; enters when price breaks and closes beyond the tunnel in the direction of the trend.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `FastEMA` | int | 20 | Fast EMA period (inner tunnel) |
| `SlowEMA` | int | 50 | Slow EMA period (outer tunnel) |
| `ConfirmBars` | int | 2 | Bars to confirm breakout |
| `RiskPercent` | double | 1.0 | Risk per trade |
| `SL_ATR_Mult` | double | 1.5 | Stop loss ATR multiple |
| `TP_ATR_Mult` | double | 3.0 | Take profit ATR multiple |
| `UseTrailing` | bool | true | Enable trailing stop |
| `MagicNumber` | int | 100004 | Unique EA identifier |

### 1.5 GridScalper_EA

**File**: `mql5/experts/GridScalper_EA.mq5`
**Strategy**: Grid-based scalping with fixed interval orders and optional martingale lot scaling.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `GridSpacing` | int | 50 | Distance between grid levels (points) |
| `MaxGridLevels` | int | 10 | Maximum concurrent grid orders |
| `InitialLots` | double | 0.01 | Starting lot size |
| `LotMultiplier` | double | 1.0 | Lot multiplier per level (1.0=no martingale) |
| `TakeProfit` | int | 30 | TP per order in points |
| `MaxDrawdownPct` | double | 10.0 | Max drawdown % before grid closes |
| `Direction` | int | 0 | 0=Both, 1=Buy only, 2=Sell only |
| `MagicNumber` | int | 100005 | Unique EA identifier |

### 1.6 IFVG_EA (Inverse Fair Value Gap)

**File**: `mql5/experts/IFVG_EA.mq5`
**Strategy**: Trades Inverse Fair Value Gaps - enters when price fills a gap in the opposite direction of the gap's formation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `GapLookback` | int | 30 | Bars to scan for inverse FVGs |
| `MinGapPips` | double | 5.0 | Minimum gap size in pips |
| `EntryType` | int | 0 | 0=Limit at gap edge, 1=Market on touch |
| `RiskPercent` | double | 1.0 | Risk per trade |
| `SL_Points` | int | 150 | Stop loss in points |
| `TP_Points` | int | 300 | Take profit in points |
| `MaxOrders` | int | 3 | Maximum concurrent orders |
| `MagicNumber` | int | 100006 | Unique EA identifier |

### 1.7 Other EAs (Summary)

| EA Name | File | Strategy Type |
|---------|------|--------------|
| `PivotVwap_EA` | `PivotVwap_EA.mq5` | Pivot points + VWAP confluence |
| `GoldFibDirectional_EA` | `GoldFibDirectional_EA.mq5` | Fibonacci golden ratio directional |
| `GoldFibHedge_EA` | `GoldFibHedge_EA.mq5` | Fibonacci golden ratio hedged |
| `DonchianVol_EA` | `DonchianVol_EA.mq5` | Donchian channel + volume breakout |
| `ElliottWave_EA` | `ElliottWave_EA.mq5` | Elliott Wave pattern detection |
| `MultiTF_Dashboard_EA` | `MultiTF_Dashboard_EA.mq5` | Multi-timeframe trend display (no trading) |
| `BoxStrategy_PD_Pro_EA` | `BoxStrategy_PD_Pro_EA.mq5` | Box breakout + premium/discount zones |
| `Structure_FVG_Execution_EA` | `Structure_FVG_Execution_EA.mq5` | Market structure + FVG execution |
| `SmartRenko_BoxPD_EA` | `SmartRenko_BoxPD_EA.mq5` | Smart Renko + box premium/discount |
| `SDM_EA` | `SDM_EA.mq5` | SuperTrend + MACD + ADX combined |
| `EMA200_ZeroLag_AlgoAlpha_EA` | `EMA200_ZeroLag_AlgoAlpha_EA.mq5` | Zero-lag EMA 200 AlgoAlpha variant |

---

## 2. Pine Script Strategies

### 2.1 EMA200Squeeze_Strategy

**File**: `pinescript/EMA200Squeeze_Strategy.pine`
**Version**: Pine Script v5

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EMA Length` | 200 | EMA period for squeeze detection |
| `Exit Mode` | "Candle Close" | "Candle Close" or "Candle Touch" for exit trigger |
| `Use SuperTrend` | false | Enable SuperTrend trailing stop |
| `ST Period` | 10 | SuperTrend period |
| `ST Multiplier` | 3.0 | SuperTrend ATR multiplier |
| `Use ADX Filter` | false | Enable ADX directional filter |
| `ADX Period` | 14 | ADX period |
| `ADX Threshold` | 20 | Minimum ADX value for entry |
| `Enable Partial Booking` | true | Enable multi-level profit booking |
| `TP1 (%)` | 1.0 | Take profit 1 distance (% from entry) |
| `TP1 Close (%)` | 40 | Percentage of position closed at TP1 |
| `TP2 (%)` | 2.0 | Take profit 2 distance |
| `TP2 Close (%)` | 30 | Percentage closed at TP2 |
| `TP3 (%)` | 3.0 | Take profit 3 distance |
| `TP3 Close (%)` | 30 | Percentage closed at TP3 |
| `Use Trailing SL` | false | Enable trailing stop loss |
| `Trailing Trigger (%)` | 1.5 | Profit % to activate trailing |
| `Trailing Offset (%)` | 0.5 | Trailing distance below peak |

### 2.2 GoldFibDirectional_Strategy

**File**: `pinescript/GoldFibDirectional_Strategy.pine`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Fib Lookback` | 50 | Bars for Fibonacci calculation |
| `Entry Level` | 0.618 | Fibonacci retracement entry level |
| `SL Level` | 0.786 | Fibonacci stop loss level |
| `TP Level` | 0.0 | Fibonacci take profit level (0 = extension) |
| `Extension Target` | 1.618 | Fibonacci extension for TP |
| `Risk %` | 1.0 | Risk per trade |

### 2.3 GoldFibHedge_Strategy

**File**: `pinescript/GoldFibHedge_Strategy.pine`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Fib Lookback` | 50 | Bars for Fibonacci calculation |
| `Hedge Ratio` | 0.5 | Hedge position size ratio |
| `Entry Level` | 0.618 | Primary entry Fib level |
| `Hedge Trigger` | 0.786 | Level to trigger hedge entry |
| `Combined TP` | 1.0 | Combined position TP as Fib extension |

### 2.4 PivotVwapEma_Strategy

**File**: `pinescript/PivotVwapEma_Strategy.pine`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Pivot Type` | "Traditional" | Pivot point calculation method |
| `EMA Fast` | 9 | Fast EMA period |
| `EMA Slow` | 21 | Slow EMA period |
| `Use VWAP` | true | Require VWAP confluence |
| `VWAP Source` | "Close" | VWAP calculation source |
| `Risk %` | 1.0 | Risk per trade |

### 2.5 SmartRenkoLike_Engine

**File**: `pinescript/SmartRenkoLike_Engine.pine`
**Type**: Indicator (no trading signals)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Brick Size` | 10 | Renko brick size in points |
| `ATR Brick` | false | Use ATR for dynamic brick sizing |
| `ATR Period` | 14 | ATR period for dynamic bricks |
| `Show Wicks` | true | Display wicks on Renko bars |

---

## 3. ReyConnector

### 3.1 Services

| Service | Port | Base URL |
|---------|------|----------|
| Control API | 5241 | `http://localhost:5241` |
| Webhook Ingest | 5242 | `http://localhost:5242` |
| Gateway | 5243 | `http://localhost:5243` |

### 3.2 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REYCONNECTOR_CONTROL_API_BASE_URL` | `http://localhost:5241` | Control API base URL |

### 3.3 API Reference

#### Control API (port 5241)

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| GET | `/api/v1/connections` | List active connections | - |
| GET | `/api/v1/signals` | Retrieve full signal log | - |
| POST | `/api/internal/v1/signals` | Ingest a signal (internal) | `IncomingAlertEnvelope` |

#### Webhook Ingest (port 5242)

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| POST | `/v1/webhook?connection_id={id}` | Receive TradingView alert | Raw text body |

#### Gateway (port 5243)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |

### 3.4 Data Models

**IncomingAlertEnvelope**:
```json
{
  "id": "uuid",
  "connectionId": "conn-demo-001",
  "rawBody": "demo,buy,EURUSD",
  "idempotencyKey": "optional-key",
  "receivedAtUtc": "2026-04-09T12:00:00Z"
}
```

**ConnectionSummary**:
```json
{
  "connectionId": "conn-demo-001",
  "status": "active",
  "lastSignalAt": "2026-04-09T12:00:00Z"
}
```

**BrokerCommand**:
```json
{
  "type": "noop"
}
```

### 3.5 Execution Engine Protocol

The execution engine is pluggable. Implement the protocol:
```python
class ExecutionEngineProtocol:
    async def process(
        self,
        connection_id: str,
        alert: IncomingAlertEnvelope,
        metadata: dict | None = None
    ) -> list[BrokerCommand]:
        ...
```

Current: `DefaultExecutionEngine` returns `NoopCommand` (Phase 6 stub).

---

## 4. MT5 Trade Segregator

### 4.1 Rule Engine

**Config File**: `tools/mt5-trade-segregator/rules/default-rules.json`

#### Rule Structure

```json
{
  "version": 1,
  "uncategorizedId": "uncategorized",
  "categories": [
    {
      "id": "string",
      "label": "Display Name",
      "match": "all | any",
      "conditions": [...]
    }
  ]
}
```

#### Match Mode

| Mode | Description |
|------|-------------|
| `all` | ALL conditions must be true (AND logic) |
| `any` | ANY condition can be true (OR logic) |

#### Condition Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `lt` | Less than | `{"field": "duration_minutes", "op": "lt", "value": 15}` |
| `lte` | Less than or equal | `{"field": "profit", "op": "lte", "value": 0}` |
| `gt` | Greater than | `{"field": "volume", "op": "gt", "value": 1.0}` |
| `gte` | Greater than or equal | `{"field": "duration_minutes", "op": "gte", "value": 1440}` |
| `eq` | Equals | `{"field": "magic", "op": "eq", "value": 100001}` |
| `between` | Range (inclusive) | `{"field": "profit", "op": "between", "min": -5, "max": 5}` |
| `contains` | String contains | `{"field": "symbol", "op": "contains", "value": "USD"}` |

#### Available Fields

| Field | Type | Description |
|-------|------|-------------|
| `duration_minutes` | float | Trade hold time in minutes |
| `profit` | float | Trade P&L (in account currency) |
| `volume` | float | Lot size |
| `magic` | int | EA magic number (0 = manual trade) |
| `deal_type` | int | 0=BUY, 1=SELL |
| `entry` | int | 0=EXIT, 1=ENTRY |
| `symbol` | string | Instrument name (e.g., "EURUSD") |

#### Default Categories

| Category | ID | Condition |
|----------|----|-----------|
| Scalping | `scalping` | duration < 15 minutes |
| Intraday | `intraday` | 15 min <= duration < 1440 min (24h) |
| Swing | `swing` | duration >= 1440 minutes |
| Uncategorized | `uncategorized` | No rule matched |

### 4.2 Deal Export Format (JSON)

```json
{
  "ticket": 123456,
  "symbol": "EURUSD",
  "magic": 100001,
  "volume": 0.10,
  "profit": 45.50,
  "swap": -5.00,
  "commission": -10.00,
  "dealTime": "2026-04-09 15:30:00",
  "dealType": 0,
  "entry": 1,
  "durationMinutes": 125.5,
  "categoryId": "intraday",
  "categoryLabel": "Intraday",
  "manualCategoryId": "",
  "manualCategoryLabel": ""
}
```

---

## 5. Market Sentiment Dashboard

### 5.1 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Groq API key (primary AI provider) |
| `ANTHROPIC_API_KEY` | - | Claude API key (fallback) |
| `OPENAI_API_KEY` | - | OpenAI API key (second fallback) |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Claude model to use |
| `NEWS_API_KEY` | - | NewsAPI key for news articles |
| `CACHE_TTL` | 300 | Analysis cache TTL in seconds |
| `MAX_NEWS_ARTICLES` | 10 | Max news articles per symbol |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | 8000 | Server port |

### 5.2 AI Provider Fallback Chain

```
1. Groq (fast, free tier)
   |-- fail --> 2. Anthropic Claude
                   |-- fail --> 3. OpenAI GPT
                                   |-- fail --> 4. Neutral template response
```

### 5.3 Cache Strategy

| Data Type | TTL | Scope |
|-----------|-----|-------|
| Symbol Analysis | 5 minutes | Per symbol |
| News Articles | 4 hours | Per symbol |
| Economic Calendar | 12 hours | Global |

### 5.4 Analysis Output Model

```
SymbolAnalysis
├── symbol: string
├── display_name: string
├── group: string
├── price
│   ├── current_price: float
│   ├── change: float
│   └── change_pct: float
├── technical
│   ├── pivot: float
│   ├── supports: [float]
│   ├── resistances: [float]
│   ├── rsi_14: float
│   ├── macd_signal: BULLISH|BEARISH|NEUTRAL
│   ├── trend_signal: UPTREND|DOWNTREND|SIDEWAYS
│   └── atr: float
├── news: [NewsArticle]
├── events: [EconomicEvent]
└── analysis
    ├── summary: string (AI generated)
    ├── direction: BULLISH|BEARISH|NEUTRAL
    ├── confidence: float (0.0-1.0)
    ├── key_levels: dict
    ├── recommendation: BUY|SELL|HOLD
    ├── news_sentiment: string
    └── economic_impact: string
```

---

## 6. Stock Scanner

### 6.1 API Endpoints

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| POST | `/api/scanner/start` | - | Start background scan |
| GET | `/api/scanner/status` | - | Progress % and status |
| GET | `/api/scanner/results/{category}` | `page`, `per_page`, `min_score`, `sector`, `sort_by` | Paginated results |
| GET | `/api/scanner/stock/{symbol}` | - | Single stock details |
| GET | `/api/scanner/sectors` | - | Sector breakdown |
| GET | `/api/scanner/sessions` | - | Historical scan sessions |
| GET | `/api/scanner/schedule` | - | Cron schedule info |

### 6.2 Scoring Categories

| Category | ID | Min Score | Description |
|----------|----|-----------|-------------|
| Multibagger | `multibagger` | 75 | High growth + strong momentum |
| Investment | `investment` | 65 | Value + stability |
| Swing (Medium) | `swing_medium` | 60 | Technical setup for medium-term swing |
| Swing (Short) | `swing_short` | 60 | Bearish setup for short positions |

### 6.3 Scoring Components

| Component | Weight | Factors |
|-----------|--------|---------|
| Technical Score | ~40% | RSI, MACD signal, trend direction, support/resistance proximity |
| Fundamental Score | ~30% | P/E ratio, debt/equity, ROE, recent earnings |
| AI Insight Score | ~30% | Claude analysis of news + chart pattern recognition |

### 6.4 Query Parameters for Results

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 20 | Results per page |
| `min_score` | float | 0 | Minimum overall score filter |
| `sector` | string | - | Filter by sector |
| `sort_by` | string | "score" | Sort field: score, technical_score, price, pe_ratio |

---

## 7. ML Models

### 7.1 Feature Engineering

**File**: `models/feature_engineering/features.py`

| Feature | Parameters | Description |
|---------|-----------|-------------|
| EMA_9 | period=9 | 9-period Exponential Moving Average |
| EMA_20 | period=20 | 20-period EMA |
| EMA_50 | period=50 | 50-period EMA |
| EMA_200 | period=200 | 200-period EMA |
| RSI_14 | period=14 | Relative Strength Index |
| ATR_14 | period=14 | Average True Range |
| SuperTrend | period=10, mult=3.0 | SuperTrend indicator (direction + bands) |
| MACD | fast=12, slow=26, signal=9 | MACD line, signal line, histogram |
| Bollinger_Upper | period=20, std=2.0 | Upper Bollinger Band |
| Bollinger_Lower | period=20, std=2.0 | Lower Bollinger Band |
| Volume_SMA | period=20 | Volume simple moving average |

### 7.2 Training Parameters

**File**: `models/training/train_model.py`

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| Symbol | `--symbol` | `GC=F` | Yahoo Finance ticker |
| Period | `--period` | `2y` | Historical data period |
| Interval | `--interval` | `1h` | Bar interval |
| TP Points | `--tp-points` | 20 | Points for target label (1 = price rises this much within 4 bars) |

### 7.3 Model Output

| Field | Type | Description |
|-------|------|-------------|
| `probability` | float (0.0-1.0) | Confidence of entry signal |
| `signal` | bool | True if probability >= 0.5 |

### 7.4 Supported Symbols (Default Training Set)

```
GC=F        Gold Futures
XAU=F       Gold Spot
EURUSD=X    EUR/USD Forex
GBPUSD=X    GBP/USD Forex
SPY         S&P 500 ETF
QQQ         Nasdaq 100 ETF
AAPL        Apple Inc.
```

---

## 8. Trading Dashboard

### 8.1 Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/login` | POST | Returns JWT token |

**Request**: `{ "username": "...", "password": "..." }`
**Response**: `{ "access_token": "jwt...", "token_type": "bearer" }`

All subsequent requests require: `Authorization: Bearer <token>`

### 8.2 Trade Upload

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/upload/trades` | POST | Upload CSV/Excel trade data |

**Required CSV columns**:
```
ticket, open_time, close_time, symbol, type, lots,
open_price, close_price, sl, tp, profit, commission,
swap, comment, magic
```

### 8.3 Attribution System

Trades are attributed to one or more of:
- **Trader**: The person who placed/manages the trade
- **Strategy**: The algorithm or strategy used
- **Guest**: External signal providers

Attribution fields:
| Field | Type | Description |
|-------|------|-------------|
| `category_type` | string | `trader`, `strategy`, or `guest` |
| `category_id` | int | FK to trader/strategy/guest table |
| `attribution_level` | float | Percentage of credit (0-100) |
| `confidence` | float | Attribution confidence (0.0-1.0) |
| `is_primary` | bool | Primary attribution flag |

### 8.4 Risk Metrics

| Metric | Description |
|--------|-------------|
| `daily_pnl` | P&L for the current trading day |
| `daily_drawdown` | Max drawdown within the day |
| `var_95` | Value at Risk (95% confidence) |
| `sharpe_ratio` | Risk-adjusted return ratio |

### 8.5 Execution Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/execution/pause` | POST | Pause all live trading |
| `/api/v1/execution/resume` | POST | Resume live trading |

---

## 9. Configuration Files

### 9.1 Broker Configuration (`configs/broker_config.example.yaml`)

```yaml
zerodha:
  api_key: ""
  api_secret: ""

angel_one:
  api_key: ""
  client_id: ""
  password: ""
  totp_secret: ""

fyers:
  app_id: ""
  access_token: ""

interactive_brokers:
  host: "127.0.0.1"
  port: 7497
  client_id: 1

alpaca:
  api_key: ""
  api_secret: ""
  base_url: "https://paper-api.alpaca.markets"

binance:
  api_key: ""
  api_secret: ""

bybit:
  api_key: ""
  api_secret: ""

metatrader5:
  login: 0
  password: ""
  server: ""
```

### 9.2 Symbols (`configs/symbols.yaml`)

| Group | Examples |
|-------|---------|
| `indian_equity.nifty50` | RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK |
| `indian_indices` | NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY |
| `forex.majors` | EURUSD, GBPUSD, USDJPY, USDCHF |
| `forex.crosses` | EURGBP, EURJPY |
| `crypto.spot` | BTC/USDT, ETH/USDT, SOL/USDT |
| `crypto.futures` | BTC/USDT:USDT, ETH/USDT:USDT |
| `us_equity.large_cap` | AAPL, MSFT, GOOGL, AMZN, NVDA |

### 9.3 Timeframes (`configs/timeframes.yaml`)

| Category | Timeframes |
|----------|-----------|
| Scalping | 1m, 3m, 5m |
| Intraday | 15m, 30m, 1h |
| Swing | 4h, 1D |
| Positional | 1W, 1M |

Each timeframe maps across platforms: TradingView, MQL5, and Freqtrade identifiers.

---

## 10. Report Builder

### 10.1 Strategy Report (`scripts/build_strategy_report.py`)

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `STRAT_FILTER` | "" (all) | Filter to specific strategy tag |

#### Input
- MT5 exported Excel file with sheets: Deals, Orders, Results

#### Output
- `strategy_analysis_N.xlsx` with per-strategy breakdown

#### Metrics Computed

| Metric | Description |
|--------|-------------|
| Total Trades | Number of round-trip trades |
| Win Rate | Percentage of profitable trades |
| Profit Factor | Gross profit / gross loss |
| Sharpe Ratio | Risk-adjusted return (annualized) |
| Max Drawdown | Maximum peak-to-trough decline |
| CAGR | Compound annual growth rate |
| Avg Duration | Average trade hold time |
| Avg Win | Average winning trade size |
| Avg Loss | Average losing trade size |
| Best Trade | Largest single trade profit |
| Worst Trade | Largest single trade loss |

### 10.2 Demo Report (`scripts/build_demo_strategy_report.py`)

Generates a sample report with synthetic data for testing the report template.

```bash
python scripts/build_demo_strategy_report.py
# Output: strategy_analysis_demo.xlsx
```
