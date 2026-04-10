# AlgoStrategies - Architecture Diagram

## High-Level System Architecture

```
+===========================================================================+
|                         ALGOSTRATEGIES PLATFORM                           |
+===========================================================================+
|                                                                           |
|  SIGNAL GENERATION LAYER                                                  |
|  +-----------------------+  +------------------+  +-------------------+   |
|  |   TradingView         |  |   MetaTrader 5   |  |   ML Models       |   |
|  |   (Pine Script)       |  |   (MQL5 EAs)     |  |   (LightGBM/ONNX) |   |
|  |                       |  |                   |  |                   |   |
|  | - EMA200Squeeze       |  | - FVG_Regime_EA   |  | - Feature Eng.    |   |
|  | - GoldFibDirectional  |  | - EMA200Squeeze   |  | - Train/Validate  |   |
|  | - GoldFibHedge        |  | - SmartMoney_EA   |  | - ONNX Export     |   |
|  | - PivotVwapEma        |  | - EMATunnel_EA    |  | - Inference       |   |
|  | - SmartRenkoLike      |  | - GridScalper_EA  |  |                   |   |
|  |                       |  | - + 22 more EAs   |  |                   |   |
|  +-----------+-----------+  +--------+---------+  +---------+---------+   |
|              |                       |                      |             |
|              | Webhook Alert         | Direct Execution     | Signals     |
|              v                       v                      v             |
|  +-----------+-------------------------------------------------------+   |
|  |                    EXECUTION & ROUTING LAYER                       |   |
|  |                                                                    |   |
|  |  +---------------------+    +----------------------------------+  |   |
|  |  |   ReyConnector      |    |   Execution Engine               |  |   |
|  |  |   (Python/FastAPI)  |    |   (execution/)                   |  |   |
|  |  |                     |    |                                  |  |   |
|  |  | Webhook    Control  |    | - Order Management System       |  |   |
|  |  | Ingest     API      |    | - Broker API Adapters           |  |   |
|  |  | :5242      :5241    |    | - Webhook Receivers              |  |   |
|  |  |     Gateway :5243   |    | - Scheduler / Cron Jobs          |  |   |
|  |  +---------------------+    +----------------------------------+  |   |
|  +--------------------------------------------------------------------+   |
|              |                                                            |
|              | Trade Orders / Deal History                                |
|              v                                                            |
|  +-----------+-------------------------------------------------------+   |
|  |                  POST-TRADE ANALYSIS LAYER                         |   |
|  |                                                                    |   |
|  |  +---------------------+    +----------------------------------+  |   |
|  |  | MT5 Trade Segregator|    |   Trading Dashboard              |  |   |
|  |  |                     |    |   (FastAPI + PostgreSQL)          |  |   |
|  |  | MQL5 EA (export)    |    |                                  |  |   |
|  |  |   +                 |    | - Multi-account P&L              |  |   |
|  |  | .NET WPF Desktop    |    | - Trade Attribution              |  |   |
|  |  | (categorize deals)  |    | - Risk Metrics                   |  |   |
|  |  | (rule engine)       |    | - Execution Control              |  |   |
|  |  +---------------------+    +----------------------------------+  |   |
|  +--------------------------------------------------------------------+   |
|              |                                                            |
|              v                                                            |
|  +-----------+-------------------------------------------------------+   |
|  |                  MARKET INTELLIGENCE LAYER                         |   |
|  |                                                                    |   |
|  |  +----------------------------+  +-----------------------------+  |   |
|  |  | Market Sentiment Dashboard |  |   Stock Scanner             |  |   |
|  |  | (FastAPI + AI)             |  |   (Background Process)      |  |   |
|  |  |                            |  |                             |  |   |
|  |  | - Price/OHLCV Feeds        |  | - S&P 500 Universe          |  |   |
|  |  | - Technical Levels         |  | - Technical Scoring         |  |   |
|  |  | - News Integration         |  | - Fundamental Scoring       |  |   |
|  |  | - Economic Calendar        |  | - AI Insight (Claude)       |  |   |
|  |  | - AI Analysis              |  | - Multi-factor Ranking      |  |   |
|  |  |   (Groq/Claude/OpenAI)    |  | - SQLite Storage            |  |   |
|  |  +----------------------------+  +-----------------------------+  |   |
|  +--------------------------------------------------------------------+   |
|                                                                           |
|  INFRASTRUCTURE & DATA LAYER                                              |
|  +--------------------------------------------------------------------+  |
|  | configs/         | Broker creds, symbols, timeframes (YAML)        |  |
|  | data/            | Market data pipeline (raw -> processed)         |  |
|  | backtesting/     | Engine, results, reports, exports               |  |
|  | research/        | Notebooks, alpha signals, statistical tests     |  |
|  | risk_management/ | Position sizing, portfolio optimization         |  |
|  | tests/           | Unit, integration, strategy validation          |  |
|  | docs/            | Templates, setup guides, strategy docs          |  |
|  +--------------------------------------------------------------------+  |
+===========================================================================+
```

## Component Dependency Map

```
                    +------------------+
                    |  configs/        |
                    |  (YAML configs)  |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
  +-------+------+  +-------+------+  +--------+-------+
  | Pine Script   |  |  MQL5 EAs    |  |  ML Models     |
  | (TradingView) |  | (MetaTrader) |  | (Python/ONNX)  |
  +-------+------+  +-------+------+  +--------+-------+
          |                  |                  |
          |  webhook         |  direct          |  signals
          v                  v                  v
  +-------+------------------+------------------+-------+
  |              ReyConnector (Alert Router)             |
  |  webhook_ingest -> control_api -> execution_engine   |
  +---------------------------+-------------------------+
                              |
                              v
  +---------------------------+-------------------------+
  |                    Broker / MT5                       |
  +---------------------------+-------------------------+
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
  +----------+----------+           +----------+----------+
  | Trade Segregator     |           | Trading Dashboard   |
  | (Categorization)     +---------->| (P&L / Attribution) |
  +----------+----------+   CSV     +----------+----------+
             |                                 |
             v                                 v
  +----------+----------+           +----------+----------+
  | backtesting/         |           | Risk Management     |
  | (Reports & Exports)  |           | (Limits & Sizing)   |
  +---------------------+           +---------------------+

  +---------------------+           +---------------------+
  | Market Sentiment     |           | Stock Scanner       |
  | Dashboard            |           | (Background)        |
  | (AI-Powered)         |           | (Multi-factor)      |
  +---------------------+           +---------------------+
        (Independent services - feed research & decision-making)
```

## Service Port Map

| Service                        | Port | Protocol | Description                    |
|-------------------------------|------|----------|--------------------------------|
| ReyConnector Control API      | 5241 | HTTP     | Signal management & connections|
| ReyConnector Webhook Ingest   | 5242 | HTTP     | TradingView alert receiver     |
| ReyConnector Gateway          | 5243 | HTTP     | Health check & service info    |
| Market Sentiment Dashboard    | 8000 | HTTP     | AI market analysis UI          |
| Stock Scanner                 | 8001 | HTTP     | US stock screening service     |
| Trading Dashboard Backend     | 8000 | HTTP     | P&L and attribution API        |
| PostgreSQL (Trading Dashboard)| 5432 | TCP      | Trade database                 |

## Technology Stack

```
+-------------------+--------------------------------------------------+
|  LAYER            |  TECHNOLOGIES                                     |
+-------------------+--------------------------------------------------+
|  Trading          |  MQL5, Pine Script v5, Freqtrade (planned)       |
|  Platforms        |                                                   |
+-------------------+--------------------------------------------------+
|  Alert Routing    |  Python 3.11+, FastAPI, Pydantic v2, httpx,      |
|                   |  async/await, uvicorn                            |
+-------------------+--------------------------------------------------+
|  Desktop App      |  .NET 10, WPF, C#, JSON rule engine              |
+-------------------+--------------------------------------------------+
|  Dashboards       |  FastAPI, SQLAlchemy, Alembic, PostgreSQL,       |
|                   |  SQLite, React/Vue (frontend)                    |
+-------------------+--------------------------------------------------+
|  AI / ML          |  LightGBM, scikit-learn, ONNX Runtime,           |
|                   |  Groq API, Anthropic Claude, OpenAI              |
+-------------------+--------------------------------------------------+
|  Data             |  yfinance, NewsAPI, Polygon, pandas, numpy       |
+-------------------+--------------------------------------------------+
|  DevOps           |  Docker, Render, Alembic migrations, Git         |
+-------------------+--------------------------------------------------+
|  Config           |  YAML, .env, JSON schemas                        |
+-------------------+--------------------------------------------------+
```
