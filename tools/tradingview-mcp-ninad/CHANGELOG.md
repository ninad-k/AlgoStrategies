# Changelog

All notable changes to tradingview-mcp-ninad will be documented in this file.

> This project was conceived and built by Ninad K. as an original idea.

## [0.2.0] — 2026-04-10

### Added
- **Trade Execution Layer** — 12 new MCP tools (total: 90)
  - `trade_execute`, `trade_close`, `trade_close_all`, `trade_modify`
  - `trade_positions`, `trade_orders`, `trade_cancel_order`
  - `trade_account`, `trade_history`
  - `trade_set_mode`, `trade_get_mode`, `trade_broker_status`
- **4 Broker Adapters** with paper/testnet support
  - Alpaca (US stocks + crypto) — `alpaca-py`
  - Binance (crypto spot + futures) — `python-binance`
  - MetaTrader 5 (forex, CFDs) — `MetaTrader5` (lazy import)
  - Interactive Brokers (multi-asset) — `ib_insync`
- **Built-in Paper Broker** — in-memory simulator with P&L tracking, SL/TP, trade logging
- **ExecutionManager** — symbol routing (crypto→Binance, stocks→Alpaca, forex→MT5, futures→IBKR), mode gating, position limits
- **3 Execution Modes** — `paper` (built-in, default), `paper_broker` (broker testnet), `live` (gated)
- **execution_config.json** — Pydantic-validated configuration for brokers, routing, and safety limits
- **8 CLI commands** — `tv trade`, `tv positions`, `tv account`, `tv close-position`, `tv set-mode`, `tv get-mode`, `tv broker-status`, `tv trade-history`
- Trade logging to `~/.tradingview-mcp-ninad/trades/` as JSONL

### Safety
- Default mode is `paper` — no API keys needed, no real money risk
- Live mode requires explicit `confirm=true` parameter
- Position limits: `max_open_positions` and `max_position_size` enforced
- All broker dependencies are optional (`pip install 'tradingview-mcp-ninad[brokers]'`)

---

## [0.1.0] — 2026-04-09

### Added
- Initial release of tradingview-mcp-ninad
- 78 MCP tools across 15 modules: health, chart, data, indicators, pine, replay, morning, watchlist, batch, capture, drawing, alerts, pane, tab, ui
- CDP connection layer with singleton management, liveness probes, and Tenacity retry
- API path verification and caching system for TradingView's undocumented internals
- Pydantic v2 rules.json configuration model with validation
- Morning brief workflow: watchlist scan, indicator reading, bias assessment
- structlog file-only logging (stdout-safe for MCP stdio transport)
- `tv` CLI with 18 commands (typer + rich)
- Platform launch scripts for macOS, Windows, and Linux
- CLAUDE.md tool selection decision tree
- Complete developer documentation suite

### Technical Decisions
- Python 3.11+ chosen over Node.js for AlgoStrategies ecosystem compatibility (ADR-001)
- FastMCP (official SDK) chosen over raw JSON-RPC (ADR-002)
- pychrome chosen for CDP communication (ADR-003)
- structlog with file-only sink to prevent MCP transport corruption (ADR-004)

---

*Maintained by Ninad K.*
