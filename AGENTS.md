# Agent context (Cursor & other AI assistants)

This file mirrors the launch targets in `.claude/launch.json` and documents where things live so future sessions stay consistent.

## Repository map

- **Pine / MT5 / Freqtrade / options / ML / execution**: top-level folders as described in `README.md`.
- **Monitoring dashboards**: `monitoring/dashboards/` — each app is self-contained (Python server + static client where applicable).
- **Tools**: `tools/` (e.g. Pine backtester UI under `tools/backtester/`).
- **Documentation**: `docs/` — component-specific subfolders; dashboard write-ups live under `docs/dashboards/`.

## Runnable services (local dev)

Run from the **working directory** shown; install deps with `pip install -r requirements.txt` in that folder when needed.

| Name | Working directory | Command | Default port |
|------|-------------------|---------|--------------|
| Market Sentiment Dashboard | `monitoring/dashboards/market_sentiment` | `python run.py` | 8000 |
| Stock Scanner | `monitoring/dashboards/stock_scanner` | `python start.py` | 8001 |
| Backtester | `tools/backtester` | `python run.py` | 8002 |

Environment: copy each app’s `.env.example` to `.env` and set API keys as required.

## Deploy (Render)

The **Market Sentiment Dashboard** service is defined in the **repository root** `render.yaml` (`rootDir: ./monitoring/dashboards/market_sentiment`). Do not add a second copy of that spec under the app folder.

## Conventions for AI edits

- Do **not** put AI assistant or tool names in code comments (including attribution or signatures).
- Prefer matching existing patterns in the file you edit (imports, logging, structure).

## Cursor-specific

Project rules live in `.cursor/rules/` (`.mdc` files with YAML frontmatter). Use them for stack- or folder-specific guidance.
