# Changelog

All notable changes to tradingview-mcp-ninad will be documented in this file.

> This project was conceived and built by Ninad K. as an original idea.

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
