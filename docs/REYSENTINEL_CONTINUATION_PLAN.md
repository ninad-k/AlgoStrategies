# ReySentinel — Continuation Plan

> **Purpose:** resume work from any machine without re-establishing context.
> Read this top-to-bottom. Every path in this document is checked against
> `origin/main` at commit `abd0aeb` (SDLC reorganization). If a fact looks
> stale, trust the code.

**Last updated:** 2026-04-19
**Resume from commit:** `abd0aeb Reorganize repository into SDLC structure`

---

## 0. Read this before anything else

The repo has been reorganized into an SDLC layout (`apps/`, `shared/`,
`deploy/`, `platforms/`, `research/`, etc.). **The reorganization moved files
but did not update import statements.** Until that is fixed,
`apps/services/rey_sentinel/app.py` will fail at import time. See **Tier 0**
in section 4 — fix that first.

A previous work session produced an `adaptive_learning/` subsystem plus a
`SignalValidator` and `KellySizer` that targeted the 80% win-rate goal. That
code was never pushed and has been discarded against this plan's direction,
but the **design** is preserved in section 5 so it can be rebuilt cleanly
against the new structure. If you are the author and want the original
source, it's on the local archive branch of the machine this was authored
from: `archive/reysentinel-adaptive-pre-sdlc-20260419` (not pushed). Do not
depend on recovering it — rebuild from section 5.

---

## 1. What ReySentinel is

Self-contained Python trading platform. Multi-model ensemble (Gemma 4 +
LLaMA 3 + ONNX) drives paper/live trading on MT5, with a heatmap dashboard,
multi-account console, and an adaptive-learning layer that tunes parameters
from realized outcomes.

Three long-running services:

| Service | Port | Entrypoint |
|---|---|---|
| Trading engine | 8060 | `apps/services/rey_sentinel/app.py` |
| Heatmap dashboard | 8061 | `apps/dashboards/portfolio_heatmap/server.py` |
| Multi-account console | 8062 | `apps/operations/multi_account_console/server.py` |

Docker / Kubernetes in `deploy/intelligence_suite/`.

---

## 2. File map (post-reorganization)

| Purpose | Path |
|---|---|
| Service package (app.py, config.yaml, README) | `apps/services/rey_sentinel/` |
| Ensemble + analyzers | `shared/ml/ensemble/` |
| Pattern recognition (CNN + ONNX trainer) | `shared/ml/pattern_recognition/` |
| RiskManager | `shared/risk/risk_manager.py` |
| Indicators (30+ via pandas_ta) | `shared/analytics/indicators.py` |
| Regime detector | `shared/analytics/regime/` |
| Correlation engine | `shared/analytics/correlation/` |
| Volume profile | `shared/analytics/volume_profile/` |
| Sentiment bridge (Reddit/RSS/F&G) | `shared/data/sentiment/` |
| Database wrapper | `shared/data/db.py` |
| Broker abstraction | `shared/execution/broker.py` |
| MT5 connector | `shared/execution/mt5_connector.py` |
| Logging bootstrap | `shared/ops/logging_config.py` |
| Audit logger / reconciler | `shared/ops/audit/` |
| Portfolio heatmap UI + API | `apps/dashboards/portfolio_heatmap/` |
| Multi-account console | `apps/operations/multi_account_console/` |
| Docker / K8s | `deploy/intelligence_suite/` |
| Backtester | `apps/tools/backtester/` |
| Legacy Gemma trader (reference) | `shared/execution/execution/gemma_trader/` |

Note: `adaptive_learning/` does **not** exist on main. Rebuild it under
`shared/ml/adaptive_learning/` (see section 5).

---

## 3. Integration contract — single source of truth

Before editing anything that touches trade state, re-read
`shared/risk/risk_manager.py` end-to-end (≈220 lines). These are the real
attribute and method names. The previous iteration hallucinated several of
these; do not reintroduce the mistakes.

### `RiskManager` — public surface you will actually use

| Member | Type / signature | Notes |
|---|---|---|
| `current_threshold` | `float` | The live confidence threshold. **Not** `confidence_threshold`. |
| `trading_cfg["max_position_size_pct"]` | `float` | Position size lives in the config dict, not on the object. Tune by mutating the dict; RiskManager reads it per-call in `calculate_position_size`. |
| `cooled_down_symbols[symbol]` | `dict[str, datetime]` | Per-symbol cooldown map. **Not** a single `cooldown_until` attribute. |
| `can_trade(decision, market_data)` | `(bool, reason)` | Gatekeeper. Call before every execution. |
| `calculate_position_size(balance, atr, sl_atr_mult, symbol)` | `dict` | Returns `{qty, risk_amount, sl_distance}`. |
| `register_trade(trade)` | `None` | Call AFTER broker fills. Appends to `logs/trades.json`. |
| `record_outcome(trade, close_price, profit)` | `dict` | Call on position close. Writes `logs/trade_outcomes.json`. This is the file downstream analytics must read. |
| `adjust_threshold(win_rate, total_trades)` | `None` | The only callable adapter of `current_threshold`. Delegate from the tuner; do not set `current_threshold` directly. |

### `setup_logging`
`from shared.ops.logging_config import setup_logging`
Signature: `setup_logging(level: str = "INFO", log_dir: str = "logs") -> None`.
**Not** `setup_logging(config)`.

### File-path invariants
`config.yaml` keys must match module expectations:

| config key | consumed by |
|---|---|
| `logging.outcome_log` | `RiskManager.outcome_log_path` → TradeReviewer (to be rebuilt) |
| `logging.decision_log` | ensemble decisions + TradeReviewer join |
| `logging.adaptive_context` | `GemmaAnalyzer._load_adaptive_context`, `LlamaAnalyzer` — the prompt addendum file |
| `logging.parameter_adjustments` | threshold / weight adjustment audit trail |

If any of these drift, adaptive context silently stops flowing into LLM
prompts. Add an integration test covering the round trip before shipping
changes here.

---

## 4. Prioritized backlog — do things in this order

### Tier 0 — fix the broken reorganization (blocker, ~1 hour)
The SDLC move renamed files but left `apps/services/rey_sentinel/app.py`
pointing at pre-move module paths. Service will not import until these are
fixed. Replacements:

| Old import | New import |
|---|---|
| `from shared.logging_config import setup_logging` | `from shared.ops.logging_config import setup_logging` |
| `from shared.indicators import calculate_indicators` | `from shared.analytics.indicators import calculate_indicators` |
| `from shared.risk_manager import RiskManager` | `from shared.risk.risk_manager import RiskManager` |
| `from shared.broker import create_broker` | `from shared.execution.broker import create_broker` |
| `from shared.mt5_connector import MT5Connector` | `from shared.execution.mt5_connector import MT5Connector` |
| `from shared.db import Database` | `from shared.data.db import Database` |
| `from ensemble.ensemble_engine import EnsembleEngine` | `from shared.ml.ensemble.ensemble_engine import EnsembleEngine` |
| `from regime_detector.detector import RegimeDetector` | `from shared.analytics.regime.detector import RegimeDetector` |
| `from volume_profile.realtime_tracker import RealtimeVolumeTracker` | `from shared.analytics.volume_profile.realtime_tracker import RealtimeVolumeTracker` |
| `from heatmap_dashboard.server import create_app` | `from apps.dashboards.portfolio_heatmap.server import create_app` |

Also check `shared/ml/ensemble/gemma_analyzer.py`, `llama_analyzer.py` —
verify `_load_adaptive_context` still finds the configured path.
**Verification:** `python -c "from apps.services.rey_sentinel.app import load_config; print('OK')"`.

### Tier 1 — adaptive layer (rebuild, ~1–2 days)
Recreate under `shared/ml/adaptive_learning/` using the design in section 5.
Avoid the hallucinations in section 6.

### Tier 2 — 80% win-rate filters (~2–3 days, highest impact)
- **A1. Multi-timeframe confirmation.** New `shared/analytics/mtf_filter.py`.
  Block M1 signals that disagree with M15 trend. Hook in between
  `SignalValidator` and `KellySizer`.
- **A2. Spread/slippage filter.** In `SignalValidator`, query
  `mt5.symbol_info(symbol).spread` and reject when `spread > ATR * 0.15`.
  Biggest silent killer of scalping win rate.
- **B6. Partial take-profits.** Extend the broker contract in
  `shared/execution/broker.py` to accept a
  `partial_tp_levels: list[dict]` argument (e.g. `[{"r": 1.0, "fraction": 0.5}]`).
  PaperBroker simulates; MT5Broker issues modify orders. This single change
  converts 55% strategies into 75%+ closed-trade systems.

### Tier 3 — reliability & edge preservation (2–3 days each)
- **B4. Top-3 symbol restriction.** Weekly APScheduler job ranks symbols by
  per-symbol Sharpe via `TradeReviewer.get_per_symbol_stats` and overwrites
  `trading.allowed_symbols` with the top 3. Persist history for audit.
- **B5. Session filtering.** Combine hour-of-day win rate with symbol to
  produce `(symbol, session)` map; wire into `SignalValidator`.
- **A3. News blackout.** Poll
  `https://nfs.faireconomy.media/ff_calendar_thisweek.xml`, cache in Redis,
  30-min blackout either side of high-impact events.
- **C7. High-confidence HOLD veto.** In `EnsembleEngine._weighted_average`,
  if any analyzer returns HOLD with confidence ≥ 0.80 AND session drawdown
  > 5%, force HOLD regardless of vote.

### Tier 4 — production hardening
- **C8.** Regime-specific weight sets per model; pick set by
  `shared/analytics/regime/detector.py` output.
- **C9.** Weekly online ONNX retrain. Wire
  `shared/ml/pattern_recognition/trainer.py` to APScheduler; feed
  `logs/trade_outcomes.json` as labeled data; blue/green swap in
  `OnnxAnalyzer`.
- **D10.** Walk-forward validator under `apps/tools/walk_forward_validator/`.
  Rolling train/test windows, per-window Sharpe and win rate. Gate on this
  before any prod config change.
- **D11.** Shadow mode — run filter + sizer in parallel with live for 2
  weeks; compare would-have-traded vs did-trade.
- **D12.** Weekly + monthly PnL circuit breakers in `RiskManager`.

### Realistic expectation
With Tier 1 rebuild + Tier 2 alone:
- acceptance rate drops ~50% → 10–15% (this is a feature, not a bug)
- closed-trade win rate should climb from ensemble baseline (60–65%) to
  75–80%
- expectancy improves more than win rate — that is the real target

---

## 5. Rebuild specification for `shared/ml/adaptive_learning/`

This is what the module should look like after Tier 1. Six files. Each is
small, single-purpose, and integrates with `RiskManager` rather than
duplicating its state.

### `trade_reviewer.py` — read-only analytics
- Reads `logs/trade_outcomes.json` (written by `RiskManager.record_outcome`).
- Reads `logs/ensemble_decisions.json` (written by the performance tracker).
- Public API:
  - `get_stats(symbol=None, days=7) -> dict` — win rate, PF, expectancy,
    Sharpe, Sortino, max drawdown, consecutive win/loss streaks.
  - `get_model_accuracy(days=7) -> dict[model_name, {correct, total, accuracy}]`
    — **join by `(symbol, entry_time)` and only credit a model when its
    predicted direction matches the executed direction AND `profit > 0`**.
    Do not compare actions against literal "win"/"loss" strings.
  - `get_per_symbol_stats(days=7) -> dict[symbol, stats]`.
  - `get_by_hour_of_day(days=30) -> dict[hour, {total, wins, win_rate, pnl}]`.
- Does **not** own any files of its own. Do not call `mkdir` on
  `logging.outcome_log` — that key is a file path, not a directory.

### `parameter_tuner.py`
- `should_tune(trade_count)` — gated by `adaptive.review_every_n_trades`
  and `adaptive.min_trades_for_adaptation`.
- `tune(ensemble_engine, risk_manager)`:
  1. Call `risk_manager.adjust_threshold(win_rate, total_trades)` — do
     **not** set `current_threshold` directly.
  2. Rebalance `ensemble_engine.models_cfg[name]["weight"]` based on
     per-model accuracy. Normalize to sum=1, clamp to
     `[min_model_weight, max_model_weight]`.
  3. Tune `config["trading"]["max_position_size_pct"]`. Halve it when
     `max_drawdown_pct >= 10`; raise it when `pf >= 1.5 and win_rate >= 0.55`.
- Persists a change log to `logs/tuner_adjustments.json`.

### `performance_tracker.py`
- In-memory session metrics only. Takes `initial_balance` from
  `broker.get_balance()` at construction — do not fabricate a default from
  config.
- `record_signal(signal, accepted, rejection_reason="")` — buffers a bounded
  deque (maxlen 500) of decisions.
- `get_metrics()` returns acceptance rate, rejection reason histogram,
  balance peak/trough, drawdown %, total return %.
- `flush_to_file()` merges buffer into `logs/ensemble_decisions.json`
  (TradeReviewer will join on this later).

### `context_generator.py`
- `generate_context(window_days=7) -> str`.
- Writes the output to the path at `logging.adaptive_context` (file, default
  `logs/adaptive_context.txt`). `GemmaAnalyzer` and `LlamaAnalyzer` already
  load this file into their system prompts — do not change the path without
  updating the analyzers in lockstep.

### `signal_validator.py` (new — the 80% lever)
Seven checks, each returning `(ok, note, weight)`. Pass threshold is a
weighted score (default 0.60).

| Check | Weight | Logic |
|---|---|---|
| R/R ratio | 0.15 | `tp_distance_atr / sl_distance_atr >= min_rr_ratio` (default 1.5) |
| Confluence | 0.25 | For BUY: RSI 40–70, MACD > signal, EMA_fast > EMA_slow, close > EMA_slow, ADX ≥ 20, Supertrend up. ≥ `min_confluence` (default 3) must hit. Symmetric for SELL. |
| Regime | 0.15 | Reject directional trades when regime is ranging or volatile. Prefer injected `regime_detector`; fall back to ADX heuristic. |
| Volume | 0.15 | `volume / volume_sma_20 >= min_volume_ratio` (default 0.8). |
| Time of day | 0.10 | Reject hours where the reviewer's 30-day map shows `total >= 5 and win_rate < 40%`. Cache for 1 hour. |
| Correlation | 0.10 | `correlated_open_same_direction < max_correlated_open` (default 2). Use correlation_engine if injected, else same-symbol heuristic. |
| ADX trend | 0.10 | `ADX_14 >= min_adx` (default 18). |

Return `{passed, score, reasons, breakdown}`. `score` in [0, 1] is also used
by KellySizer to scale sizing.

### `kelly_sizer.py` (new)
Fractional Kelly from realized edge:
```
full_kelly = p - (1 - p) / b   # p = win rate, b = avg_win/avg_loss
size_pct   = clamp(full_kelly * kelly_fraction * confidence * validator_score * 100, floor, ceiling)
```
Defaults: `kelly_fraction=0.25`, `min_trades=20`, floor `0.25%`, ceiling
`2.0%`. Bootstraps to `config.trading.max_position_size_pct * confidence *
validator_score` until `min_trades` is reached.

### Ensemble test runner wiring
Place the new runner at `apps/services/rey_sentinel/test_ensemble_live.py`.
Pipeline for each symbol on each cycle:

```
1. fetch candles (MT5Connector or skip)
2. calculate_indicators()
3. ensemble.analyze(indicators) -> signal
4. HOLD -> record, return
5. risk_manager.can_trade(decision, market_data) -> bool
   FAIL -> record rejection, return
6. signal_validator.validate(signal, indicators, open_positions)
   FAIL -> record rejection, return
7. kelly_sizer.recommend_size_pct(symbol, confidence, validator_score)
8. overwrite config["trading"]["max_position_size_pct"] temporarily,
   call risk_manager.calculate_position_size(...), restore.
9. broker.place_order(...)
10. risk_manager.register_trade(trade)
```
**Do not** skip step 5. **Do not** try to compute exit prices by indexing
backward in the dataframe — exits come from the broker (SL/TP hit or
explicit close).

### Config additions
```yaml
adaptive:
  min_trades_per_model: 3
  min_model_weight: 0.10
  max_model_weight: 0.60
  min_position_size_pct: 0.25
  max_position_size_pct_cap: 2.0

signal_validator:
  enabled: true
  min_score: 0.60
  min_confluence: 3
  min_rr_ratio: 1.5
  min_adx: 18.0
  require_regime_alignment: true
  require_volume_confirmation: true
  min_volume_ratio: 0.8
  avoid_weak_hours: true
  max_correlated_open: 2

kelly_sizer:
  enabled: true
  kelly_fraction: 0.25
  min_trades: 20
  min_size_pct: 0.25
  max_size_pct: 2.0
```

Tune these in walk-forward (D10) before changing prod.

---

## 6. Hallucinations to NOT reintroduce

These are the mistakes a previous iteration made. Keep this list in view
whenever touching the adaptive layer.

| Wrong | Right |
|---|---|
| `risk_manager.confidence_threshold` | `risk_manager.current_threshold` |
| `risk_manager.max_position_size_pct` | `risk_manager.trading_cfg["max_position_size_pct"]` |
| `risk_manager.cooldown_until = ts` | `risk_manager.cooled_down_symbols[symbol] = datetime` |
| `setup_logging(config)` | `setup_logging(level, log_dir)` |
| `Path("logs/trades.json").mkdir(...)` | `Path("logs/trades.json").parent.mkdir(...)` |
| `TradeReviewer` keeps its own `outcomes` dict | Reads the file `RiskManager.record_outcome` writes |
| Credit model when `predicted_action == "BUY" and outcome == "win"` | Credit only when predicted direction == executed direction AND `profit > 0`, joined by `(symbol, timestamp)` |
| Test runner skips `RiskManager.can_trade()` | `can_trade` is the gatekeeper — call it |
| Exit price = `df.iloc[-N]["close"]` | Exits come from broker (SL/TP hit or explicit close); never from backward-indexing the entry dataframe |

---

## 7. How to resume on a new machine

```bash
# 1. Clone
git clone https://github.com/ninad-k/AlgoStrategies.git
cd AlgoStrategies

# 2. venv + deps
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r apps/services/rey_sentinel/requirements.txt

# 3. Sanity-check current state — this SHOULD fail until Tier 0 is done
python -c "from apps.services.rey_sentinel.app import load_config; print('OK')"
#    If ImportError on shared.logging_config / shared.risk_manager / etc.,
#    proceed to Tier 0 before anything else.

# 4. Read, in this order:
#    - docs/REYSENTINEL_CONTINUATION_PLAN.md (this file)
#    - shared/risk/risk_manager.py  (the integration contract)
#    - apps/services/rey_sentinel/app.py  (where imports need fixing)
#    - shared/ml/ensemble/ensemble_engine.py  (consumer of the tuner)

# 5. Do Tier 0. Verify imports succeed.

# 6. Pick up Tier 1 (rebuild adaptive_learning using section 5).
```

### Running the service after Tier 0
```bash
# Paper mode
python -m apps.services.rey_sentinel.app --mode paper

# Specific symbols
python -m apps.services.rey_sentinel.app --symbols BTCUSD ETHUSD --mode paper

# Dashboards only
python -m apps.services.rey_sentinel.app --dashboard-only
```

### Running the Docker stack
```bash
cd deploy/intelligence_suite/scripts
./deploy.sh up       # build + start
./deploy.sh status
./deploy.sh logs
./deploy.sh down
```

---

## 8. Open questions / deferred decisions

1. **Live broker choice.** MT5 Python bindings are Windows-only. For Linux
   production deployment, need Interactive Brokers or cTrader adapter. Not
   started.
2. **Dashboard authentication.** Endpoints are open. Fine for localhost,
   unacceptable for any exposed deployment. Add JWT middleware to
   `apps/dashboards/portfolio_heatmap/server.py` and
   `apps/operations/multi_account_console/server.py`.
3. **Persistence.** Everything is JSON files today. Above ~10k trades/month
   this gets slow. Swap `RiskManager` logging onto TimescaleDB (already in
   requirements).
4. **Ollama in Docker.** Compose stack expects Ollama on the host
   (`host.docker.internal:11434`). Linux VM without GPU needs a separate
   Ollama container with a smaller model.
5. **Mobile app.** Directory scaffolding exists under the old layout; not
   carried into the new SDLC structure. Decide whether to rebuild under
   `apps/mobile/` or drop from scope.

---

## 9. First 60 minutes on the new PC — checklist

- [ ] Clone, venv, install.
- [ ] Run the sanity snippet (section 7 step 3). Expect it to fail.
- [ ] Read `shared/risk/risk_manager.py` end-to-end (≈220 lines).
- [ ] Read `apps/services/rey_sentinel/app.py` imports (≈20 lines).
- [ ] Read section 6 (hallucinations) one more time.
- [ ] Execute Tier 0 — rewrite the 10 imports in `app.py`.
- [ ] Verify sanity snippet now prints `OK`.
- [ ] Start Tier 1 — create `shared/ml/adaptive_learning/` and build the
      six files from section 5 (start with `trade_reviewer.py`, since all
      others depend on it).

You should be productive within the hour.
