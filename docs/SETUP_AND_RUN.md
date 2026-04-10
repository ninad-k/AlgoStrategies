# AlgoStrategies - Setup & Run Guide

## Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | 3.11+ | All Python services, ML models, scripts |
| .NET SDK | 10.0+ | MT5 Trade Segregator desktop app |
| MetaTrader 5 | Latest | MQL5 EAs, MetaEditor for compilation |
| TradingView | Pro+ | Pine Script strategies (webhook alerts) |
| Docker | 24+ | Trading Dashboard, ReyConnector production |
| PostgreSQL | 15+ | Trading Dashboard (or use Docker) |
| Node.js | 18+ | Frontend dashboards |
| Git | 2.40+ | Version control |

---

## 1. Initial Repository Setup

```bash
# Clone
git clone https://github.com/ninad-k/AlgoStrategies.git
cd AlgoStrategies

# Python virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Environment variables
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# Edit .env with your API keys

# Broker configuration
copy configs\broker_config.example.yaml configs\broker_config.yaml
# Edit with your broker API keys
```

### Environment Variables (.env)

| Variable | Description | Required By |
|----------|-------------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | Monitoring |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for alerts | Monitoring |
| `DISCORD_WEBHOOK_URL` | Discord webhook for notifications | Monitoring |
| `WEBHOOK_SECRET` | Secret for webhook authentication | ReyConnector |
| `WEBHOOK_PORT` | Port for webhook listener (default: 8080) | ReyConnector |
| `DB_URL` | Database connection string | Trading Dashboard |
| `NSE_DATA_API_KEY` | NSE market data access | Options strategies |
| `BINANCE_API_KEY` | Binance exchange API key | Crypto trading |
| `BINANCE_API_SECRET` | Binance exchange API secret | Crypto trading |
| `GROQ_API_KEY` | Groq API for fast AI analysis | Sentiment Dashboard |
| `ANTHROPIC_API_KEY` | Claude API for AI analysis | Sentiment Dashboard |
| `NEWS_API_KEY` | NewsAPI for market news | Sentiment Dashboard |

---

## 2. Market Sentiment Dashboard

The AI-powered market analysis dashboard with technical levels, news, and economic calendar.

### Setup

```bash
cd monitoring/dashboards/market_sentiment

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Set at minimum one AI key: GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY
# Set NEWS_API_KEY for news integration
```

### Run

```bash
# Start the dashboard
python run.py

# Or manually with uvicorn
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

**Access**: http://localhost:8000

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/symbols` | Available symbol groups and defaults |
| GET | `/api/analysis/{symbol}` | Full AI analysis for a symbol |
| GET | `/api/dashboard` | Bulk analysis for multiple symbols |
| GET | `/api/news/{symbol}` | Raw news articles |
| GET | `/api/calendar` | Upcoming economic events |
| POST | `/api/refresh/{symbol}` | Force cache invalidation |
| GET | `/api/health` | Service health & AI provider status |
| POST | `/api/scanner/start` | Start background stock scan |
| GET | `/api/scanner/status` | Scanner progress percentage |
| GET | `/api/scanner/results/{category}` | Scan results by category |
| GET | `/api/scanner/stock/{symbol}` | Single stock scan details |
| GET | `/api/scanner/sectors` | Sector breakdown |

### Production Deployment (Render)

Already configured in `render.yaml`:
```bash
# Deploys automatically when pushed to main
# Service: market-sentiment-dashboard
# Set env vars in Render dashboard: GROQ_API_KEY, ANTHROPIC_API_KEY, NEWS_API_KEY
```

---

## 3. ReyConnector (TradingView -> MT5 Bridge)

Three-service microservice architecture for routing TradingView webhook alerts to MT5.

### Setup

```bash
cd tools/reyconnector-python

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# Install with dev dependencies
pip install -e ".[dev]"
```

### Run (Local Development)

**Option A: All 3 services at once**
```bash
./scripts/start-local.sh
```

**Option B: Individual services (each in a separate terminal)**
```bash
# Terminal 1: Control API
uvicorn reyconnector.apps.control_api:app --port 5241 --reload

# Terminal 2: Webhook Ingest
uvicorn reyconnector.apps.webhook_ingest:app --port 5242 --reload

# Terminal 3: Gateway
uvicorn reyconnector.apps.gateway:app --port 5243 --reload
```

### Test Webhook

```bash
# Send a test alert
curl -X POST "http://localhost:5242/v1/webhook?connection_id=conn-demo-001" \
  -H "Content-Type: text/plain" \
  -d "demo,buy,EURUSD"

# Check signal log
curl http://localhost:5241/api/v1/signals

# Check connections
curl http://localhost:5241/api/v1/connections
```

### Production Deployment (Docker)

```bash
cd tools/reyconnector-python

# Build
docker build -f infra/docker/Dockerfile.control-api -t reyconnector:latest .

# Run
docker run -p 5241:5241 reyconnector:latest
```

### TradingView Webhook Setup

1. Create an alert on your TradingView strategy
2. Set webhook URL: `https://your-domain.com/v1/webhook?connection_id=your-conn-id`
3. Set alert message format: `strategy_name,action,symbol`
4. Example: `ema200squeeze,buy,EURUSD`

---

## 4. MT5 Trade Segregator

### 4a. MQL5 Expert Advisor (runs inside MetaTrader 5)

#### Install

1. Copy files to your MT5 data folder:
   ```
   tools/mt5-trade-segregator/mql5/Include/TradeSegregator/
     -> Copy to: <MT5_DATA>/MQL5/Include/TradeSegregator/

   tools/mt5-trade-segregator/mql5/Experts/TradeSegregator/
     -> Copy to: <MT5_DATA>/MQL5/Experts/TradeSegregator/

   tools/mt5-trade-segregator/rules/rules-for-ea.csv
     -> Copy to: <MT5_DATA>/MQL5/Files/rules-for-ea.csv
   ```

2. Open MetaEditor -> Open `TradeSegregatorEA.mq5` -> Compile (F7)

3. Drag EA onto any chart in MT5

#### EA Input Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `InpFrom` | datetime | 30 days ago | History start date |
| `InpTo` | datetime | now | History end date |
| `InpRulesFile` | string | `rules-for-ea.csv` | Path to rules CSV in MQL5/Files/ |
| `InpOutputPrefix` | string | `trade_segregator` | Output filename prefix |
| `InpExportOnInit` | bool | true | Auto-export when EA loads |
| `InpTimerSeconds` | int | 0 | Periodic export interval (0=disabled) |

#### Output Files (in MQL5/Files/)

- `trade_segregator_deals.json` - Full deal data with categories
- `trade_segregator_deals.csv` - Flat CSV for spreadsheet import

### 4b. Desktop Application (.NET WPF)

#### Prerequisites

- Windows 10/11
- .NET 10 SDK: https://dotnet.microsoft.com/download
- Visual Studio 2022+ (with .NET desktop workload)

#### Build & Run

```bash
cd tools/mt5-trade-segregator/desktop

# Option A: Visual Studio
# Open TradeSegregator.slnx -> Set TradeSegregator.Desktop as startup -> F5

# Option B: Command line
dotnet build
dotnet run --project src/TradeSegregator.Desktop
```

#### Workflow

1. **Import**: Click "Import" -> select `trade_segregator_deals.json` from MQL5/Files/
2. **Review**: Deals table shows auto-categorized trades
3. **Manual Sort**: Switch to "Manual Sort" tab for uncategorized deals
4. **Edit Rules**: Modify `rules/default-rules.json` and re-evaluate
5. **Export**: Click "Export" to save categorized CSV

### 4c. Rules Configuration

Edit `tools/mt5-trade-segregator/rules/default-rules.json`:

```json
{
  "version": 1,
  "uncategorizedId": "uncategorized",
  "categories": [
    {
      "id": "scalping",
      "label": "Scalping",
      "match": "all",
      "conditions": [
        { "field": "duration_minutes", "op": "lt", "value": 15 }
      ]
    }
  ]
}
```

Convert JSON rules to EA-compatible CSV:
```bash
python tools/mt5-trade-segregator/scripts/rules_json_to_csv.py
# Output: rules/rules-for-ea.csv
```

---

## 5. Trading Dashboard

Full-stack P&L aggregation, trade attribution, and risk monitoring.

### Setup

```bash
cd trading-dashboard

# Option A: Docker Compose (recommended)
docker-compose up

# Option B: Manual setup
cd backend
pip install -r requirements.txt

# Database setup
# Set DB_URL in .env (PostgreSQL connection string)
alembic upgrade head    # Run migrations
```

### Run

```bash
# Docker
docker-compose up

# Manual
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Access**: http://localhost:8000

### Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | JWT login |
| POST | `/api/v1/upload/trades` | Bulk trade CSV/Excel import |
| GET | `/api/v1/traders` | List all traders |
| POST | `/api/v1/traders` | Create a trader |
| GET | `/api/v1/strategies` | List all strategies |
| POST | `/api/v1/accounts` | Link an MT5 account |
| PUT | `/api/v1/attribution-rules/{id}` | Update attribution rules |
| GET | `/api/v1/pnl/{account_id}` | Account P&L summary |
| POST | `/api/v1/execution/pause` | Pause live trading |
| POST | `/api/v1/execution/resume` | Resume live trading |
| GET | `/api/v1/admin/risk-limits` | Risk limit dashboard |

### Database Migrations

```bash
cd trading-dashboard/backend

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 6. ML Model Training & Inference

### Setup

```bash
# Install ML dependencies
pip install yfinance pandas numpy scikit-learn lightgbm onnx onnxruntime skl2onnx
```

### Train a Model

```bash
cd models/training

# Default: trains on GC=F (Gold Futures), 2 years, 1H bars
python train_model.py

# Custom symbol and period
python train_model.py --symbol AAPL --period 2y --tp-points 30

# Output: models/saved_models/ema200_squeeze.onnx
```

#### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--symbol` | `GC=F` | Yahoo Finance ticker symbol |
| `--period` | `2y` | Data period (1y, 2y, 5y, max) |
| `--interval` | `1h` | Bar interval (1m, 5m, 15m, 1h, 1d) |
| `--tp-points` | `20` | Take profit in points for target labeling |

### Run Inference

```python
from models.inference.predict import predict

result = predict("AAPL", ohlcv_dataframe)
print(result.probability)  # 0.0 - 1.0
print(result.signal)        # True/False
```

---

## 7. MQL5 Expert Advisors (MetaTrader 5)

### Install Any EA

1. Open MetaTrader 5 -> File -> Open Data Folder
2. Navigate to `MQL5/Experts/`
3. Copy the `.mq5` file from `mql5/experts/`
4. If EA uses custom includes, copy from `mql5/include/` to `MQL5/Include/`
5. Open MetaEditor (F4) -> Open the EA -> Compile (F7)
6. Back in MT5: Navigator -> Expert Advisors -> Drag EA onto chart
7. Ensure "AutoTrading" is enabled (toolbar button)
8. Configure input parameters in the EA properties dialog

### Common EA Parameters (most EAs share these)

| Parameter | Description |
|-----------|-------------|
| `RiskPercent` | Risk per trade as % of account equity |
| `FixedLots` | Fixed lot size (overrides risk-based if > 0) |
| `StopLoss` | Stop loss in points or ATR multiples |
| `TakeProfit1/2/3` | Partial TP levels |
| `ClosePercent1/2/3` | % of position to close at each TP |
| `TrailingStart` | Points in profit before trailing activates |
| `TrailingStep` | Trailing stop step size |
| `MaxDailyTrades` | Maximum trades per day |
| `MaxSpread` | Maximum allowed spread to enter |
| `MagicNumber` | Unique ID for this EA instance |
| `SessionStart/End` | Trading session time filter |
| `UseHTFFilter` | Enable higher-timeframe trend filter |

---

## 8. Pine Script Strategies (TradingView)

### Install

1. Open TradingView -> Pine Editor (bottom panel)
2. Click "Open" -> Paste strategy code from `pinescript/`
3. Click "Add to Chart"
4. Open Settings gear icon to configure parameters

### Set Up Webhook Alerts

1. Right-click the strategy on chart -> "Add Alert"
2. Condition: Select your strategy
3. Check "Webhook URL" and enter your ReyConnector endpoint:
   ```
   https://your-domain.com/v1/webhook?connection_id=your-id
   ```
4. Message format: `{{strategy.order.action}},{{ticker}},{{close}}`
5. Click "Create"

---

## 9. Backtesting & Reports

### Generate Strategy Report from MT5 Export

```bash
cd scripts

# Using MT5 export file
python build_strategy_report.py

# Filter by strategy
STRAT_FILTER=combo python build_strategy_report.py

# Demo report (sample data)
python build_demo_strategy_report.py
```

### Output
- `strategy_analysis_N.xlsx` with per-strategy sheets
- Metrics: total trades, win rate, profit factor, Sharpe, max drawdown, CAGR

### Organize Backtest Results

Follow the naming convention:
```
backtesting/results/<platform>/<STRATEGY>_<SYMBOL>_<TIMEFRAME>_<DATERANGE>.<ext>

Example:
backtesting/results/pinescript/EMA200Squeeze_EURUSD_15m_20240101-20241231.json
backtesting/results/mql5/FVG_Regime_XAUUSD_1H_20240101-20241231.html
```

---

## 10. Options Strategies (Indian Markets)

### Market Hours (IST)

| Event | Time |
|-------|------|
| Pre-open | 09:00 |
| Market Open | 09:15 |
| Market Close | 15:30 |
| Post-close | 16:00 |

### Weekly Expiry Schedule

| Index | Expiry Day |
|-------|-----------|
| NIFTY | Thursday |
| BANKNIFTY | Thursday |
| FINNIFTY | Tuesday |
| MIDCPNIFTY | Monday |

### Structure (templates ready, implementations pending)

```
options/
├── strategies/          # Strategy implementation scripts
├── payoff_diagrams/     # P&L visualization
├── greeks_analysis/     # Greeks tracking
├── chain_data/          # Option chain snapshots
└── templates/           # Strategy boilerplate
```

---

## Quick Reference: Start Everything

```bash
# Terminal 1: Market Sentiment Dashboard
cd monitoring/dashboards/market_sentiment && python run.py

# Terminal 2-4: ReyConnector
cd tools/reyconnector-python && ./scripts/start-local.sh

# Terminal 5: Trading Dashboard
cd trading-dashboard && docker-compose up

# MetaTrader 5: Attach EAs to charts via Navigator panel
# TradingView: Add Pine strategies via Pine Editor
```
