# Rey Capital - Gemma Trader Deployment Guide

Complete deployment scripts for the AI-powered trading bot. This guide covers installation, running, and stopping the application.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Running the Application](#running-the-application)
5. [Stopping the Application](#stopping-the-application)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Gemma Trader is an AI-powered cryptocurrency trading bot that combines:

- **AI Model**: Google's Gemma 4 LLM (running locally via Ollama)
- **Broker**: MetaTrader 5 (MT5) or other supported brokers
- **Strategy**: 1-minute crypto scalping with 30+ technical indicators
- **Dashboard**: Real-time web UI at `http://localhost:8050`
- **Self-Learning**: Adaptive strategy that learns from trade history

### Supported Trading Modes

- **Paper Mode** (Default): Simulated trading with no real money
- **Live Mode**: Real trading with actual funds (use with caution)

### System Requirements

- **Windows 10+** or compatible system
- **Python 3.8+**
- **Ollama** (for AI model)
- **MetaTrader 5** (for MT5 trading, optional for paper mode)
- **8GB RAM minimum** (16GB+ recommended)
- **GPU optional** (NVIDIA with 8GB+ VRAM recommended for faster inference)

---

## Quick Start

### For the Impatient

```powershell
# 1. Open PowerShell as Administrator
# 2. Navigate to: D:\Projects\AlgoStrategies\AlgoStrategies\execution\gemma_trader

cd D:\Projects\AlgoStrategies\AlgoStrategies\execution\gemma_trader

# 3. Run setup (one-time only)
.\Setup-GemmaTrader.ps1

# 4. Launch the trader
.\Run-GemmaTrader.ps1 -Mode paper

# 5. Open browser: http://localhost:8050

# 6. To stop, press Ctrl+C in PowerShell, or use:
.\Stop-GemmaTrader.ps1
```

---

## Installation

### Step 1: Run Setup Script

The setup script handles all initialization:

```powershell
.\Setup-GemmaTrader.ps1
```

**What it does:**
- ✓ Verifies Python 3.8+ is installed
- ✓ Creates a Python virtual environment
- ✓ Installs all dependencies from `requirements.txt`
- ✓ Installs MetaTrader5 Python library (optional)
- ✓ Checks/installs Ollama and Gemma 4 model
- ✓ Creates logs directory

**Output Example:**
```
  ╔═══════════════════════════════════════════════════════╗
  ║     REY CAPITAL - GEMMA TRADER SETUP WIZARD           ║
  ║     Complete Environment Installation                ║
  ╚═══════════════════════════════════════════════════════╝

  Step 1: System Requirements Check
  [✓] Python found: Python 3.11.5
  [✓] Git found: git version 2.40.0

  Step 2: Ollama & Gemma Model Setup
  [i] Checking Ollama service...
  [!] Ollama is not running
  [i] Attempting to start Ollama...
  [✓] Ollama service started successfully
  [i] Pulling gemma4 model (this may take a few minutes)...
  [✓] Gemma model pulled successfully

  ...
```

### Step 2: Verify Installation

After setup completes, you should see:

```
  ╔═══════════════════════════════════════════════════════╗
  ║              SETUP COMPLETE                           ║
  ╚═══════════════════════════════════════════════════════╝

  Next steps:
  1. Run the trader:
     .\Run-GemmaTrader.ps1

  2. (Optional) For paper trading mode:
     .\Run-GemmaTrader.ps1 -Mode paper

  3. Open dashboard in browser:
     http://localhost:8050

  To stop the trader, run:
     .\Stop-GemmaTrader.ps1
```

---

## Running the Application

### Basic Usage

```powershell
# Start in paper trading mode (default)
.\Run-GemmaTrader.ps1

# OR explicitly specify mode
.\Run-GemmaTrader.ps1 -Mode paper
```

### Custom Configuration

#### Change Dashboard Port
```powershell
.\Run-GemmaTrader.ps1 -Port 8080
```

#### Trade Specific Symbols
```powershell
.\Run-GemmaTrader.ps1 -Symbols BTCUSD ETHUSD LTCUSD
```

#### Change Timeframe
```powershell
.\Run-GemmaTrader.ps1 -Interval 5m
```

#### Dashboard Only (No Trading)
```powershell
.\Run-GemmaTrader.ps1 -DashboardOnly
```

#### Use Custom Config File
```powershell
.\Run-GemmaTrader.ps1 -Config my_custom_config.yaml
```

#### Combine Multiple Options
```powershell
.\Run-GemmaTrader.ps1 -Mode paper -Port 8080 -Symbols BTCUSD ETHUSD -DashboardOnly
```

### Startup Output

When successful, you'll see:

```
  ╔═══════════════════════════════════════════════════════╗
  ║        REY CAPITAL - GEMMA TRADER LAUNCHER            ║
  ║        AI-Powered Trading Engine                      ║
  ╚═══════════════════════════════════════════════════════╝

  PREFLIGHT CHECKS
  ────────────────────────────────────────────────────────
  [✓] Python - Python 3.11.5
  [✓] Config - config.yaml
  [✓] Venv - D:\...\execution\gemma_trader\venv
  [✓] Ollama - Service running
  [✓] Port 8050 - Available

  ENVIRONMENT ACTIVATION
  ────────────────────────────────────────────────────────
  [i] Venv - Activating virtual environment...
  [✓] Venv - Activated

  LAUNCH CONFIGURATION
  ════════════════════════════════════════════════════════
  Mode              : paper
  Dashboard URL     : http://localhost:8050
  Config File       : config.yaml
  Trading Enabled   : Yes
  ════════════════════════════════════════════════════════

  STARTING APPLICATION
  ────────────────────────────────────────────────────────
  ✓ Application started. Press Ctrl+C to stop.

  2024-04-17 14:32:15,123 - rey_capital - INFO
  +==========================================================+
  |               REY CAPITAL AI BOT                        |
  +===========================================================+
  |  Dashboard:  http://localhost:8050                      |
  |  Mode:       PAPER                                      |
  |  Model:      gemma4                                     |
  |  Symbols:    BTCUSD, ETHUSD, LTCUSD                    |
  |  Interval:   1m                                         |
  +===========================================================+
```

### Accessing the Dashboard

Open your web browser and go to:

```
http://localhost:8050
```

The dashboard shows:
- Real-time trade decisions
- Open positions
- Performance metrics
- Trade history
- Gemma AI reasoning

---

## Stopping the Application

### Method 1: Graceful Shutdown (Recommended)

```powershell
.\Stop-GemmaTrader.ps1
```

This will:
- ✓ Wait up to 10 seconds for clean shutdown
- ✓ Allow pending trades to complete
- ✓ Save state and logs
- ✓ Clean up resources

**Output:**
```
  ╔═══════════════════════════════════════════════════════╗
  ║        REY CAPITAL - GEMMA TRADER SHUTDOWN            ║
  ║        Graceful Termination                           ║
  ╚═══════════════════════════════════════════════════════╝

  STOPPING GEMMA TRADER
  ────────────────────────────────────────────────────────
  [i] Scan - Looking for Gemma Trader processes...
  [✓] Found - 1 process(es) to stop

  GRACEFUL SHUTDOWN (waiting 10 seconds)
  ────────────────────────────────────────────────────────
  [i] Process - Stopping PID 12345...
  [✓] Process - Gracefully stopped (PID 12345)

  CLEANUP
  ────────────────────────────────────────────────────────
  [✓] Cleanup - PID file removed

  ╔═══════════════════════════════════════════════════════╗
  ║              SHUTDOWN COMPLETE                        ║
  ╚═══════════════════════════════════════════════════════╝
```

### Method 2: Press Ctrl+C

While the application is running, you can press **Ctrl+C** in the PowerShell window.

### Method 3: Force Kill

If graceful shutdown doesn't work:

```powershell
.\Stop-GemmaTrader.ps1 -Force
```

This immediately terminates the process without waiting for cleanup.

### Method 4: Stop Ollama Too

If you want to also stop the Ollama service:

```powershell
.\Stop-GemmaTrader.ps1 -KillOllama
```

---

## Advanced Usage

### Configuration

Edit `config.yaml` to customize:

```yaml
# ─ Server ─
server:
  port: 8050

# ─ Data Source ─
mt5_data:
  timeframe: "1m"
  n_bars: 500
  poll_interval_seconds: 60

# ─ AI Model ─
ollama:
  model: "gemma4"
  temperature: 0.1
  timeout: 120

# ─ Trading ─
trading:
  mode: "paper"  # or "live"
  confidence_threshold: 0.65
  max_position_size_pct: 1.0
  max_open_trades: 5
  allowed_symbols:
    - "BTCUSD"
    - "ETHUSD"
    - "LTCUSD"
    - "XRPUSD"
    - "SOLUSD"

# ─ Risk Management ─
risk_management:
  stop_loss_atr_multiplier: 1.0
  take_profit_atr_multiplier: 1.5
  max_daily_loss_pct: 5.0
  max_drawdown_pct: 10.0
```

### Multiple Instances

Run multiple instances on different ports:

```powershell
# Terminal 1: Main bot on port 8050
.\Run-GemmaTrader.ps1 -Port 8050 -Symbols BTCUSD ETHUSD

# Terminal 2: Secondary bot on port 8051
.\Run-GemmaTrader.ps1 -Port 8051 -Symbols LTCUSD XRPUSD
```

Access dashboards at:
- http://localhost:8050
- http://localhost:8051

### Monitoring Logs

Logs are saved to `logs/` directory:

```
logs/
├── trades.json              # Trade records
├── gemma_decisions.json     # AI decisions
├── trade_outcomes.json      # Trade results
├── adaptive_context.txt     # Learning history
└── parameter_adjustments.json # Strategy updates
```

View logs in real-time:

```powershell
# Watch trade log
Get-Content logs/trades.json -Wait

# Or use PowerShell ISE / VS Code
code logs/
```

### Environment Variables

Override settings via environment variables:

```powershell
$env:PORT = "9000"
$env:OLLAMA_HOST = "http://custom-ollama:11434"
.\Run-GemmaTrader.ps1
```

---

## Troubleshooting

### Issue: "Python not found"

**Solution:**
1. Install Python 3.8+ from https://python.org
2. **Ensure "Add Python to PATH" is checked during installation**
3. Restart PowerShell
4. Run `python --version` to verify

### Issue: "Ollama service not running"

**Solution:**
1. Download Ollama from https://ollama.com
2. Run setup again:
   ```powershell
   .\Setup-GemmaTrader.ps1
   ```
   This will auto-start Ollama
3. Or manually start:
   ```powershell
   ollama serve
   ```

### Issue: "Gemma model not found"

**Solution:**
```powershell
ollama pull gemma4
```

Wait for the model to download (~6GB).

### Issue: "Port 8050 already in use"

**Solution:**
Use a different port:
```powershell
.\Run-GemmaTrader.ps1 -Port 8080
```

Or find and stop the process using port 8050:
```powershell
Get-NetTCPConnection -LocalPort 8050
```

### Issue: "MetaTrader 5 not running"

For paper trading mode, this is optional.

For live trading:
1. Install MT5 from https://www.metatrader5.com
2. Open MT5 and log in before starting the trader
3. The trader will use MT5's data feed automatically

### Issue: "Virtual environment activation fails"

**Solution:**
Delete the venv folder and run setup again:
```powershell
Remove-Item -Path "venv" -Recurse -Force
.\Setup-GemmaTrader.ps1
```

### Issue: Application crashes with "module not found"

**Solution:**
Reinstall dependencies:
```powershell
.\Setup-GemmaTrader.ps1 -InstallDeps
```

### Issue: "Permission denied" errors

**Solution:**
Run PowerShell as Administrator:
1. Right-click PowerShell
2. Select "Run as administrator"
3. Run the scripts again

### Enable Script Execution (if needed)

If you get "execution policies prevent script execution":

```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Script Parameters Reference

### Setup-GemmaTrader.ps1

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-SkipOllama` | switch | false | Skip Ollama setup |
| `-SkipMT5` | switch | false | Skip MetaTrader 5 check |
| `-OllamaModel` | string | "gemma4" | Ollama model to pull |
| `-Verbose` | switch | false | Verbose output |

**Examples:**
```powershell
.\Setup-GemmaTrader.ps1                    # Full setup
.\Setup-GemmaTrader.ps1 -SkipOllama       # Skip Ollama
.\Setup-GemmaTrader.ps1 -OllamaModel gemma2  # Use Gemma 2 instead
```

### Run-GemmaTrader.ps1

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-Mode` | string | "paper" | Trading mode: "paper" or "live" |
| `-Port` | int | 8050 | Dashboard port |
| `-Config` | string | "config.yaml" | Config file path |
| `-Symbols` | string[] | - | Override symbols to trade |
| `-Interval` | string | - | Override timeframe (e.g., "5m") |
| `-DashboardOnly` | switch | false | Run dashboard without trading |
| `-SkipChecks` | switch | false | Skip preflight checks |
| `-Verbose` | switch | false | Verbose output |

**Examples:**
```powershell
.\Run-GemmaTrader.ps1                                    # Default paper mode
.\Run-GemmaTrader.ps1 -Mode live                        # Live trading (CAUTION)
.\Run-GemmaTrader.ps1 -Port 8080 -Symbols BTCUSD       # Custom port & symbol
.\Run-GemmaTrader.ps1 -DashboardOnly -SkipChecks       # Dashboard only, skip checks
```

### Stop-GemmaTrader.ps1

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-Force` | switch | false | Force kill without grace period |
| `-KillOllama` | switch | false | Also stop Ollama service |
| `-WaitSeconds` | int | 10 | Grace period before force kill |

**Examples:**
```powershell
.\Stop-GemmaTrader.ps1                    # Graceful shutdown (10s wait)
.\Stop-GemmaTrader.ps1 -Force              # Immediate termination
.\Stop-GemmaTrader.ps1 -KillOllama        # Also stop Ollama
.\Stop-GemmaTrader.ps1 -WaitSeconds 30    # 30s grace period
```

---

## Performance Tuning

### For Slower Systems

In `config.yaml`:
```yaml
mt5_data:
  poll_interval_seconds: 120  # Check for signals every 2 minutes
  n_bars: 200                  # Use fewer candles

ollama:
  temperature: 0.05            # More deterministic decisions
  timeout: 180                 # Increase timeout

trading:
  max_open_trades: 1           # Trade one at a time
```

### For GPU-Accelerated Systems

```yaml
ollama:
  temperature: 0.3             # More creative decisions
  num_predict: 8192            # Longer responses
```

Then restart the application to use GPU acceleration via Ollama.

---

## FAQ

**Q: Is live trading safe?**
A: Use paper mode first to test the bot. Start with small position sizes in live mode. The bot has built-in risk management.

**Q: Can I trade crypto on non-MT5 brokers?**
A: Yes, with modifications to support CCXT (Binance, Kraken, etc.). Contact support for custom integration.

**Q: How often does the bot check for signals?**
A: Default is every 60 seconds (configurable in config.yaml).

**Q: What does Gemma do?**
A: Analyzes 30+ technical indicators and decides: BUY, SELL, or HOLD with confidence levels.

**Q: Can I modify the strategy?**
A: Yes, edit the decision logic in `gemma_analyzer.py` or adjust config thresholds.

---

## Support

For issues, check logs in `logs/` directory or contact support at info@reycapitalsfo.com

---

**Version:** 1.0  
**Last Updated:** April 2024  
**Maintainer:** Rey Capital
