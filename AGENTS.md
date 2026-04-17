# Agent context (Cursor & other AI assistants)

This file mirrors the launch targets in `.claude/launch.json` and documents where things live so future sessions stay consistent.

## Repository map

- **Strategy lifecycle**: `strategies/` with `incubator/`, `candidate/`, `production/`, and `retired/`
- **Platform adapters**: `platforms/` for Pine, MT5, Freqtrade, options, and Python-oriented wrappers
- **Shared code**: `shared/` for reusable analytics, execution, risk, ML, schemas, and ops helpers
- **Apps**: `apps/` for dashboards, tools, mobile clients, and operational consoles
- **Documentation**: `docs/` for architecture, processes, templates, and strategy write-ups

## Runnable services (local dev)

Run from the **working directory** shown; install deps with `pip install -r requirements.txt` in that folder when needed.

| Name | Working directory | Command | Default port |
|------|-------------------|---------|--------------|
| Market Sentiment Dashboard | `apps/dashboards/market_sentiment` | `python run.py` | 8000 |
| Stock Scanner | `apps/dashboards/stock_scanner` | `python start.py` | 8001 |
| Backtester | `apps/tools/backtester` | `python run.py` | 8002 |
| Trading Dashboard Frontend | `apps/dashboards/trading_dashboard/frontend` | `npm run dev` | 3000 |

Environment: copy each app's `.env.example` to `.env` and set API keys as required.

## Deploy (Render)

The **Market Sentiment Dashboard** service is defined in the **repository root** `render.yaml` with `rootDir: ./apps/dashboards/market_sentiment`. Do not add a second copy of that spec under the app folder.

## Conventions for AI edits

- Do **not** put AI assistant or tool names in code comments (including attribution or signatures).
- Prefer matching existing patterns in the file you edit (imports, logging, structure).

## Cursor-specific

Project rules live in `.cursor/rules/` (`.mdc` files with YAML frontmatter). Use them for stack- or folder-specific guidance.
