# PineScript Backtester

A web-based backtesting tool that runs PineScript strategies over extended historical data and generates MQL5-style reports.

## Prerequisites

- Python 3.10+
- pip

## Setup

1. Install dependencies:

```bash
cd tools/backtester
pip install -r requirements.txt
```

2. (Optional) Copy and configure environment variables:

```bash
cp .env.example .env
```

## Running the Server

### Command Line

```bash
cd tools/backtester
py -3 run.py
```

The server starts at **http://localhost:8002**.

### PyCharm

A shared run configuration is included. Open the project in PyCharm and select **Backtester** from the run configuration dropdown, then click Run (or press Shift+F10).

The configuration runs `tools/backtester/run.py` with the working directory set to `tools/backtester/`.

## Usage

1. Open http://localhost:8002 in your browser
2. Paste your PineScript v5 strategy code
3. Configure symbol, timeframe, date range, and capital settings
4. Choose a data source:
   - **Yahoo Finance** -- auto-downloads OHLCV data (best for daily/weekly timeframes)
   - **Upload CSV** -- drag & drop your own CSV file
   - **MT5 Export Script** -- generates a configured MQL5 script to export data from MetaTrader 5
5. Click **Run Backtest**
6. View the MQL5-style report with equity curves, drawdown charts, orders, and deals

## Data Source Notes

- **Yahoo Finance intraday limits:** 1m/5m/15m data covers ~60 days; 1h covers ~730 days. For 5-10 year backtests, use daily or weekly timeframes.
- **CSV format:** requires Date, Open, High, Low, Close, Volume columns (flexible column name matching).
- **MT5 Export:** generates a `.mq5` script pre-configured with your symbol/timeframe/dates. Run it in MetaTrader 5, then upload the exported CSV.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Frontend UI |
| POST | `/api/parse` | Parse PineScript, return extracted parameters |
| POST | `/api/backtest` | Submit backtest (Yahoo Finance data) |
| POST | `/api/backtest/csv` | Submit backtest (CSV upload) |
| GET | `/api/backtest/{id}/status` | Poll backtest progress |
| GET | `/api/backtest/{id}/report` | Full report JSON |
| GET | `/api/backtests` | List previous backtests |
| DELETE | `/api/backtest/{id}` | Delete a backtest |
| GET | `/api/health` | Health check |

## Project Structure

```
tools/backtester/
├── run.py                  # Uvicorn entry point (port 8002)
├── requirements.txt
├── server/
│   ├── main.py             # FastAPI app + routes
│   ├── models.py           # Pydantic schemas
│   ├── database.py         # SQLite storage
│   ├── data.py             # yfinance download + cache
│   ├── parser/             # PineScript lexer, parser, transpiler
│   └── engine/             # Indicators, backtest loop, metrics
├── client/
│   ├── index.html          # SPA frontend
│   ├── styles.css          # Light/dark theme
│   └── app.js              # Frontend logic + charts
└── data/                   # Runtime data (gitignored)
```
