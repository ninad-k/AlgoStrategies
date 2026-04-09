# Environment Setup Guide

| Field | Value |
|---|---|
| **Author** | Ninad K. |
| **Created** | 2026-04-09 |

> This project was Ninad K.'s own original idea.

## Prerequisites

- Python 3.11 or higher
- TradingView Desktop app (free or paid)
- pip (comes with Python)

## Step-by-Step Setup

### 1. Clone and navigate

```bash
cd AlgoStrategies/tools/tradingview-mcp-ninad
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install in editable mode

```bash
pip install -e .
```

### 4. Install dev dependencies (optional)

```bash
pip install -e ".[dev]"
```

### 5. Configure trading rules

```bash
cp rules.example.json rules.json
# Edit rules.json: add your watchlist symbols, bias criteria, risk rules
```

### 6. Launch TradingView with CDP

```bash
# macOS
./scripts/launch_tv_debug_mac.sh

# Windows
scripts\launch_tv_debug.bat

# Linux
./scripts/launch_tv_debug_linux.sh
```

### 7. Verify connection

```bash
tv health
```

You should see JSON output with `"success": true` and your current chart symbol.

### 8. Register with Claude Code

Add to `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "tradingview-ninad": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "tradingview_mcp_ninad"],
      "cwd": "/absolute/path/to/tools/tradingview-mcp-ninad"
    }
  }
}
```

Restart Claude Code. Ask: "Run tv_health_check"

## Verifying Everything Works

| Check | Command | Expected |
|---|---|---|
| Package installed | `tv --help` | Shows 18 commands |
| CDP connected | `tv health` | `"cdp_connected": true` |
| Chart readable | `tv state` | Shows current symbol |
| Rules loaded | `tv brief` | Scans watchlist symbols |
| Lint clean | `ruff check src/` | No errors |

## Common Issues

| Problem | Fix |
|---|---|
| `tv_health_check` fails | TradingView not running or not launched with `--remote-debugging-port=9222` |
| "No TradingView chart target found" | Open a chart in TradingView Desktop (not just the app, but a chart tab) |
| Stale connection after TV restart | The server auto-reconnects — just retry the tool |
| `print()` corruption | Never use `print()` in server code — use structlog |

---

*Authored by Ninad K.*
