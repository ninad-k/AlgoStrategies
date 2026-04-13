# Intelligence Suite

Self-contained trading intelligence platform with multi-model ensemble, market analysis, and deployment infrastructure.

## Modules

| Module | Description | Port |
|--------|-------------|------|
| **Ensemble Engine** | Multi-model trading (Gemma 4 + LLaMA + ONNX) with weighted voting | — |
| **Regime Detector** | Classifies market as trending/ranging/volatile/breakout | — |
| **Sentiment Bridge** | Scrapes Reddit/RSS/Fear&Greed, generates directional bias | — |
| **Volume Profile** | Real-time TPO, POC, VAH/VAL, HVN/LVN | — |
| **Correlation Engine** | Rolling correlation, lead-lag detection, cointegration | — |
| **Pattern Recognition** | CNN-based chart pattern detection (12 patterns) | — |
| **Heatmap Dashboard** | Portfolio exposure, VaR, stress testing | 8061 |
| **Audit Logger** | Compliance-grade trade logging + backtest reconciliation | — |
| **Multi-Account** | Manage 10+ MT5 accounts with consolidated P&L | 8062 |
| **Deployment** | Docker + Kubernetes + deploy scripts | — |
| **Mobile App** | React Native (Expo) for iOS/Android | — |

## Quick Start

```bash
# 1. Install dependencies
cd intelligence_suite
pip install -r requirements.txt

# 2. Configure
cp config.yaml config.local.yaml
# Edit config.local.yaml with your broker/model settings

# 3. Run (paper mode)
python app.py --mode paper

# 4. Run dashboards only
python app.py --dashboard-only

# 5. Run with specific symbols
python app.py --symbols BTCUSD ETHUSD --mode paper
```

## Requirements

- Python 3.11+
- Ollama with Gemma 4 and/or LLaMA 3 models
- MetaTrader 5 desktop (for live trading)
- Node.js 18+ (for mobile app only)

## Architecture

```
app.py (entry point)
├── Trading Engine (background thread)
│   ├── MT5 Data Feed → shared/indicators.py (30+ indicators)
│   ├── Regime Detector → regime classification
│   ├── Volume Profile → POC/VAH/VAL levels
│   ├── Sentiment Bridge → directional bias
│   ├── Ensemble Engine → weighted multi-model voting
│   │   ├── Gemma 4 (aggressive scalper)
│   │   ├── LLaMA 3 (conservative analyst)
│   │   └── ONNX/LightGBM (fast rule-based)
│   ├── Risk Manager → position sizing + cooldowns
│   └── Broker → MT5/Binance/Paper execution
├── Heatmap Dashboard (FastAPI :8061)
│   ├── Portfolio Analyzer
│   ├── VaR Calculator (Historical/Parametric/Monte Carlo)
│   └── Stress Tester
├── Multi-Account Dashboard (FastAPI :8062)
│   ├── Account Manager
│   ├── Risk Allocator
│   └── Consolidated P&L
└── Audit Logger (background)
    ├── Trade/Decision/Risk logging
    └── Backtest ↔ Live reconciliation
```

## Docker Deployment

```bash
cd deployment
docker-compose up -d
```

## Mobile App

```bash
cd mobile_app
npm install
npx expo start
```

## Self-Contained Copy

To use this suite independently:
```bash
cp -r intelligence_suite/ /your/target/path/
cd /your/target/path/intelligence_suite/
pip install -r requirements.txt
python app.py --help
```
