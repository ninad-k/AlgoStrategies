# MT5 Trade Segregator

End-to-end toolkit to **export MetaTrader 5 deal history**, **assign each deal to categories** using a shared rule engine, and **manually resolve** anything that stays uncategorized.

**Location in this repo:** `tools/mt5-trade-segregator/` (AlgoStrategies).

## Layout

| Path | Purpose |
|------|---------|
| `rules/` | Canonical rule definitions (`default-rules.json`) and JSON Schema |
| `scripts/` | Helpers (e.g. JSON → CSV for the EA) |
| `mql5/` | Expert Advisor and includes — copy into your MT5 `MQL5` tree |
| `desktop/` | **.NET 10** WPF app — open `TradeSegregator.sln` on Windows |

## MetaTrader 5 (EA)

1. Copy `mql5/Include/TradeSegregator` → `<MT5 Data Folder>/MQL5/Include/TradeSegregator`
2. Copy `mql5/Experts/TradeSegregator` → `<MT5 Data Folder>/MQL5/Experts/TradeSegregator`
3. Copy `rules/rules-for-ea.csv` (generate with `scripts/rules_json_to_csv.py`) → `<MT5 Data Folder>/MQL5/Files/rules-for-ea.csv`
4. Compile `TradeSegregatorEA.mq5` in MetaEditor
5. Attach the EA to any chart. Use inputs to set the history window and output file name. The EA writes categorized deals to `MQL5/Files` (JSON + CSV).

**Rule parity:** The EA reads **CSV** rules (`rules-for-ea.csv`) so the same logical rules can be maintained from `default-rules.json` via the export script or the desktop app’s future “export for EA” action.

## Windows desktop

1. Install the **[.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)** (projects target **`net10.0`** / **`net10.0-windows`** for WPF; `desktop/global.json` pins the SDK family)
2. Open `desktop/TradeSegregator.sln`
3. Set **TradeSegregator.Desktop** as startup project and run

On non-Windows machines you can still edit the solution; building the WPF app requires the Windows targeting pack (typically on Windows).

The app can **import** JSON exports from the EA (or the same format produced manually), **reload rules** from `default-rules.json`, **re-run** categorization, and use the **Manual sort** tab to assign uncategorized deals to categories.

## Rule format

See `rules/rules.schema.json` and `rules/default-rules.json`. Categories are evaluated **top to bottom**; the **first** category whose conditions all match (`match: all`) wins. Remaining deals use `uncategorizedId`.

## Copying into MT5 folder structure

Your MetaTrader 5 data directory usually looks like:

- `.../MetaQuotes/Terminal/<instance>/MQL5/Experts/`
- `.../MetaQuotes/Terminal/<instance>/MQL5/Include/`
- `.../MetaQuotes/Terminal/<instance>/MQL5/Files/`

Place files as described above.
