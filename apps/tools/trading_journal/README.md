# Rey Capital — Scalping Trading Journal

Auto-generated, Rey Capital themed Excel journal built from MetaTrader 5 closed-trade history. The workbook is **read-only output** — it is rebuilt end-to-end on every refresh. There are no manual-entry columns in v1.

## What it is

A consolidated xlsx covering every MT5 account configured in `apps/tools/pnl_dashboard/accounts.yaml`, tuned for daily scalping review. Inside you get:

| Sheet | Content |
|---|---|
| Cover | Run metadata, accounts included, date range, headline Net P&L. |
| About | Embedded explanation — mirrors this README so the file is self-documenting. |
| Trade Log | One row per closed trade with price, P&L, holding time, session, MFE/MAE. Formatted as an Excel Table for native filter / sort. |
| Daily Summary | Per-day trades, wins, win%, gross/net P&L, expectancy, profit factor, running equity. |
| Equity Curve | Cumulative net-P&L line chart + drawdown bar below. |
| Calendar | Month grid, cells colour-scaled by daily net P&L. |
| By Hour | P&L and win% per UTC hour (0–23). Finds the productive scalping window. |
| By Session | Asia / London / London-NY Overlap / New York / Gap split. |
| By Symbol | Per-instrument performance. |
| By Weekday | Monday–Sunday bias. |
| Holding Buckets | `<30s`, `30s-2m`, `2-5m`, `5-15m`, `15m+`. |
| MFE/MAE | Per-trade MFE/MAE and a scatter of realised move vs MFE, plus average efficiency. |
| Risk Metrics | Expectancy, profit factor, max drawdown, streaks, Sharpe-of-trades, commission drag. |
| By Account | Per-account breakdown — acts as the account filter in v1. |

## How to refresh

Live MT5 (Windows, with the `MetaTrader5` Python package installed):

```bash
python -m apps.tools.trading_journal.build_journal \
    --config apps/tools/pnl_dashboard/accounts.yaml
```

Offline / CSV (any OS — rebuilds from a combined CSV already produced by `extract_mt5_data.py` or `TradeHistoryExporter_EA.mq5`):

```bash
python -m apps.tools.trading_journal.build_journal \
    --csv path/to/all_accounts_YYYYMMDD_HHMMSS.csv
```

Optional flags:

- `--output path/to/file.xlsx` — explicit output path; default is a timestamped file in `apps/tools/trading_journal/out/`.
- `--source-label "..."` — overrides the label shown on the Cover sheet.

Each run also refreshes `apps/tools/trading_journal/out/ReyCapital_ScalpingJournal_latest.xlsx` as a stable pointer to the most recent build.

## How MT5 data gets in

The CLI does **not** reinvent extraction. It imports [extract_mt5_data.py](../pnl_dashboard/extract_mt5_data.py), which:

1. Reads `accounts.yaml` and resolves `${...}` password env-vars.
2. For each account: `mt5.initialize(...)` → `mt5.history_deals_get(...)`.
3. Pairs `DEAL_ENTRY_IN` / `DEAL_ENTRY_OUT` by `position_id` (supports partial closes).
4. Enriches with MFE / MAE using M1 bars via `mt5.copy_rates_range(...)`.
5. Returns a pandas DataFrame with account metadata attached.

`build_journal.py` then hands the raw DataFrame to `transform.normalise(...)` (sessions, holding buckets, pips, efficiency ratios) and finally to `journal_writer.build_workbook(...)`.

## Metric definitions

- **Win rate** — wins / trades. Winning trade = Net P&L > 0 (after commission + swap).
- **Expectancy** — Net P&L / trades. Dollar earned per trade on average.
- **Profit factor** — gross winning P&L / |gross losing P&L|.
- **Max drawdown** — largest peak-to-trough drop in cumulative Net P&L, sequenced by trade exit time.
- **R-multiple** — price move in favour / absolute stop distance. Blank when SL was not recorded at entry (see Limitations).
- **MFE / MAE** — Maximum Favorable / Adverse Excursion in price units between entry and exit, sampled from M1 bars.
- **MFE efficiency** — realised move / MFE. 1.0 = full capture, 0.3 = left 70% on the table.
- **Session buckets (UTC exit-time)** — Asia 22-07, London 07-12, London-NY Overlap 12-16, New York 16-21, Gap 21-22.
- **Holding buckets** — scalping-calibrated: `<30s`, `30s-2m`, `2-5m`, `5-15m`, `15m+`.

## Limitations (v1)

- **Closed trades only** — open positions are filtered out.
- **No manual overlay** — no tag / emotion / screenshot / review-note columns. Adding them would require append-merge logic, which conflicts with the "rebuild from scratch" contract. Scheduled for v2 only if requested.
- **R-multiple and SL/TP-hit %** depend on SL/TP surviving on MT5 exit deals. Today `pair_deals` writes `sl=0.0 / tp=0.0` because `history_deals_get` does not return them; these columns will start populating automatically once the upstream extractor captures SL/TP from order history.
- **Session classification is UTC** — broker server-time drift is not corrected.
- **No scheduling built in.** Wrap the command in `cron` / `launchd` / Task Scheduler for recurring refreshes.

## File layout

```
apps/tools/trading_journal/
├── __init__.py
├── README.md              ← this file
├── build_journal.py       ← CLI entrypoint
├── journal_writer.py      ← openpyxl workbook builder
├── rey_theme.py           ← Rey Capital palette, fonts, shared helpers
├── transform.py           ← pure-pandas normalisation + per-bucket stats
└── out/
    ├── ReyCapital_ScalpingJournal_YYYYMMDD_HHMMSS.xlsx
    └── ReyCapital_ScalpingJournal_latest.xlsx
```

## Related assets (reused, not duplicated)

- [apps/tools/pnl_dashboard/extract_mt5_data.py](../pnl_dashboard/extract_mt5_data.py) — live MT5 pull.
- [apps/tools/pnl_dashboard/accounts.yaml](../pnl_dashboard/accounts.yaml) — account config.
- [platforms/mql5/experts/TradeHistoryExporter_EA.mq5](../../../platforms/mql5/experts/TradeHistoryExporter_EA.mq5) — nightly CSV export from inside MT5 if you prefer an EA-driven feed.
- [docs/strategy-intake/ReyCapital_Logo.png](../../../docs/strategy-intake/ReyCapital_Logo.png) — logo embedded on every sheet.
