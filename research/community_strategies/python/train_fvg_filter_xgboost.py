"""
FVG Liquidity Sweep Filter — Multi-Timeframe XGBoost ONNX
----------------------------------------------------------
Trains on **all standard MT5 chart periods**: minute frames up to M20, then
M30, H1–H4, D1, W1, MN1.

Data loading (default **last 6 months**, `FVG_TRAIN_MONTHS` / `FVG_TRAIN_YEARS`):
  - Prefer `copy_rates_range` for **every** timeframe into the lookback window.
  - If range is empty: chunked `copy_rates_from_pos` (100k bars/call) until the window
    is covered or history ends; then trim to [utc_from, utc_to].

Features (8 floats, matches FVG_LiquiditySweep_Sessions_EA_XGB.mq5):
  - EMA alignment, FVG gap/ATR, sweep strength, ATR ratio, RSI momentum,
    bar body, wick ratio, close position in range.

Output: FVG_Filter_XGB.onnx -> <terminal_data>/MQL5/Files/

Requires: MetaTrader 5 running, logged in, history available (History Center).
"""

import sys
import os
import shutil
import datetime as dt
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb
from onnxmltools.convert.common.data_types import FloatTensorType
from onnxmltools.convert import convert_xgboost


# ─── CONFIG ──────────────────────────────────────────────────────────
SYMBOL = os.environ.get("FVG_TRAIN_SYMBOL", "XAUUSD")
# Lookback: default 6 months; set FVG_TRAIN_MONTHS=6 or FVG_TRAIN_YEARS=0.5
if os.environ.get("FVG_TRAIN_YEARS"):
    TRAIN_MONTHS = int(round(float(os.environ["FVG_TRAIN_YEARS"]) * 12))
else:
    TRAIN_MONTHS = int(os.environ.get("FVG_TRAIN_MONTHS", "6"))
TRAIN_MONTHS = max(TRAIN_MONTHS, 1)

def _mt5_all_chart_timeframes():
    """All MT5 periods from M1 through monthly (skip constants missing in API)."""
    spec = [
        "M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20",
        "M30", "H1", "H2", "H3", "H4", "D1", "W1", "MN1",
    ]
    tfs, names = [], []
    for sn in spec:
        c = getattr(mt5, "TIMEFRAME_" + sn, None)
        if c is not None:
            tfs.append(c)
            names.append(sn)
    return tfs, names


TIMEFRAMES, TF_NAMES = _mt5_all_chart_timeframes()

MAX_BARS_PER_CALL = 100_000  # MetaTrader 5 limit per copy_rates_from_pos request

EMA_FAST     = 9
EMA_SLOW     = 21
EMA_TREND    = 50
ATR_PERIOD   = 14
RSI_PERIOD   = 14
FVG_LOOKBACK = 50
SWING_LOOKBACK = 20
ONNX_OPSET   = 15
MODEL_NAME   = "FVG_Filter_XGB.onnx"
N_FEATURES   = 8


def connect_mt5():
    """Initialize MT5 connection."""
    if not mt5.initialize():
        print(f"MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    info = mt5.terminal_info()
    print(f"Connected to MT5: {info.path}")
    return info.data_path


def _symbol_rank(name: str) -> int:
    """Lower = better for gold spot training (prefer USD pairs over crosses)."""
    u = name.upper()
    if "XAUUSD" in u:
        return 0
    if "XAU" in u and u.endswith("USD"):
        return 1
    if u in ("GOLD",) or ("GOLD" in u and "EUR" not in u and "GBP" not in u):
        return 2
    if "XAU" in u:
        return 3
    return 9


def resolve_training_symbol(want: str) -> str:
    """Pick a tradable symbol: use `want` if valid, else best gold/XAU from terminal."""
    if want:
        si = mt5.symbol_info(want)
        if si is not None:
            if not si.visible:
                mt5.symbol_select(want, True)
            return want

    alt = [
        "XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.a", "XAUUSD_i",
        "XAUUSD.", "XAUUSD#", "XAUUSD.r",
    ]
    for s in alt:
        si = mt5.symbol_info(s)
        if si is not None:
            mt5.symbol_select(s, True)
            print(f"Resolved symbol '{want}' -> '{s}' (set FVG_TRAIN_SYMBOL to pin a name).")
            return s

    found = []
    syms = mt5.symbols_get()
    if syms:
        for s in syms:
            u = s.name.upper()
            if "XAU" in u or u == "GOLD" or "GOLD" in u:
                found.append(s.name)
    found = sorted(set(found), key=_symbol_rank)
    if found:
        pick = found[0]
        mt5.symbol_select(pick, True)
        print(f"Resolved symbol '{want}' -> '{pick}' from terminal list ({len(found)} candidates).")
        return pick

    print("ERROR: No gold/XAU symbol found. Set env FVG_TRAIN_SYMBOL to your broker's name.")
    return want


# Approximate minutes per bar (for bar-count estimates on higher timeframes)
_TF_MINUTES = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6,
    "M10": 10, "M12": 12, "M15": 15, "M20": 20, "M30": 30,
    "H1": 60, "H2": 120, "H3": 180, "H4": 240,
    "D1": 1440, "W1": 10080, "MN1": 43200,
}


def _bars_for_window(tf_name: str) -> int:
    """Estimated bars needed to cover TRAIN_MONTHS on this timeframe."""
    total_days = TRAIN_MONTHS * (365.25 / 12.0)
    total_min = total_days * 24 * 60
    m = max(_TF_MINUTES.get(tf_name, 1440), 1)
    return int(total_min / m) + 100


def _fetch_rates_chunked_to_window(symbol: str, tf, utc_from: dt.datetime, utc_to: dt.datetime, tf_name: str):
    """
    Walk copy_rates_from_pos in 100k chunks until oldest bar is before utc_from
    or no more data. Trim to [utc_from, utc_to].
    """
    target_ts = int(utc_from.timestamp())
    pieces = []
    pos = 0
    max_bars = max(_bars_for_window(tf_name) * 2, MAX_BARS_PER_CALL * 3)

    while pos < max_bars:
        part = mt5.copy_rates_from_pos(symbol, tf, pos, MAX_BARS_PER_CALL)
        if part is None or len(part) == 0:
            if pos == 0:
                print(
                    f"    [{tf_name}] chunk fetch empty — open chart / History Center for '{symbol}'."
                )
            break
        pieces.append(part)
        oldest = int(part["time"][0])
        if oldest <= target_ts:
            break
        if len(part) < MAX_BARS_PER_CALL:
            break
        pos += len(part)

    if not pieces:
        return None
    full = np.concatenate(pieces)
    df = pd.DataFrame(full)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.sort_values("time").drop_duplicates(subset=["time"], keep="last")
    t0 = pd.Timestamp(utc_from)
    t1 = pd.Timestamp(utc_to)
    df = df[(df["time"] >= t0) & (df["time"] <= t1)]
    return df


def fetch_data_multitf(symbol: str):
    """Fetch OHLCV for all timeframes: last TRAIN_MONTHS calendar-equivalent window (UTC)."""
    utc_to = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    utc_to = utc_to.replace(microsecond=0)
    days = int(round(TRAIN_MONTHS * (365.25 / 12.0)))
    utc_from = utc_to - dt.timedelta(days=days)
    utc_from = utc_from.replace(microsecond=0)
    print(
        f"History window (UTC): {utc_from.isoformat()} -> {utc_to.isoformat()} "
        f"(~{TRAIN_MONTHS} month(s), ~{days} days)"
    )

    si = mt5.symbol_info(symbol)
    if si is None:
        print(f"ERROR: symbol_info('{symbol}') is None — cannot load rates.")
        return {}
    if not si.visible:
        mt5.symbol_select(symbol, True)

    data = {}
    for tf, name in zip(TIMEFRAMES, TF_NAMES):
        rates = mt5.copy_rates_range(symbol, tf, utc_from, utc_to)
        if rates is None or len(rates) == 0:
            df = _fetch_rates_chunked_to_window(symbol, tf, utc_from, utc_to, name)
            if df is None or len(df) == 0:
                need = min(MAX_BARS_PER_CALL, max(_bars_for_window(name), 250))
                part = mt5.copy_rates_from_pos(symbol, tf, 0, need)
                if part is None or len(part) == 0:
                    print(f"[{name}] No data. err={mt5.last_error()}")
                    continue
                df = pd.DataFrame(part)
                df["time"] = pd.to_datetime(df["time"], unit="s")
                t0 = pd.Timestamp(utc_from)
                t1 = pd.Timestamp(utc_to)
                df = df[(df["time"] >= t0) & (df["time"] <= t1)]
                if len(df) == 0:
                    print(f"[{name}] No bars in {TRAIN_MONTHS}m window after fallback.")
                    continue
        else:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")

        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)
        data[name] = df
        print(f"[{name}] Fetched {len(df)} bars")
    return data


def compute_ema(series, period):
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df, period=14):
    """Average True Range."""
    high  = df["high"]
    low   = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def compute_rsi(series, period=14):
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def detect_fvg_bullish(h, l, i, min_gap):
    """Bullish FVG at bar i: lows[i] > highs[i+2] (numpy 1d arrays)."""
    if i < 2 or i + 2 >= len(h):
        return False, 0.0
    gap = l[i] - h[i + 2]
    if gap > min_gap:
        return True, (l[i] + h[i + 2]) * 0.5
    return False, 0.0


def detect_fvg_bearish(h, l, i, min_gap):
    """Bearish FVG at bar i: highs[i] < lows[i+2]."""
    if i < 2 or i + 2 >= len(h):
        return False, 0.0
    gap = l[i + 2] - h[i]
    if gap > min_gap:
        return True, (h[i] + l[i + 2]) * 0.5
    return False, 0.0


def detect_liquidity_sweep(direction, h, l, c, i, lookback=20):
    """Swing sweep before bar i. h,l,c are numpy arrays."""
    if i < 2:
        return False, 0.0
    eff_lb = lookback
    if i < lookback + 2:
        eff_lb = min(i - 2, lookback)
    start = max(0, i - eff_lb)
    sh = h[start:i]
    sl = l[start:i]

    if direction == 1:
        swing_low = float(np.min(sl))
        if l[i - 1] <= swing_low:
            strength = max(0.5, (c[i - 1] - l[i - 1]) / (c[i - 1] - swing_low + 1e-6))
            return True, min(strength, 2.0)
    else:
        swing_high = float(np.max(sh))
        if h[i - 1] >= swing_high:
            strength = max(0.5, (h[i - 1] - c[i - 1]) / (swing_high - c[i - 1] + 1e-6))
            return True, min(strength, 2.0)

    return False, 0.0


def build_feature_matrix(df):
    """Extract 8 features per setup (numpy-accelerated inner loop)."""
    df = df.copy()

    df["ema_fast"] = compute_ema(df["close"], EMA_FAST)
    df["ema_slow"] = compute_ema(df["close"], EMA_SLOW)
    df["ema_trend"] = compute_ema(df["close"], EMA_TREND)
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df.dropna(inplace=True)

    if len(df) < FVG_LOOKBACK + 25:
        return None, None

    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    o = df["open"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    atr_a = df["atr"].to_numpy(dtype=np.float64)
    rsi_a = df["rsi"].to_numpy(dtype=np.float64)
    ema_f = df["ema_fast"].to_numpy(dtype=np.float64)
    ema_s = df["ema_slow"].to_numpy(dtype=np.float64)
    ema_t = df["ema_trend"].to_numpy(dtype=np.float64)

    n = len(df)
    min_gap_baseline = float(np.nanmedian(atr_a)) * 0.1

    features = []
    labels = []

    for i in range(FVG_LOOKBACK, n - 20):
        atrv = atr_a[i]
        if atrv <= 0:
            continue

        ef, es, et = ema_f[i], ema_s[i], ema_t[i]
        if ef > es > et:
            ema_align = 1.0
            direction = 1
        elif ef < es < et:
            ema_align = -1.0
            direction = -1
        else:
            continue

        if direction == 1:
            fvg_found, fvg_price = detect_fvg_bullish(h, l, i, min_gap_baseline)
        else:
            fvg_found, fvg_price = detect_fvg_bearish(h, l, i, min_gap_baseline)

        if not fvg_found:
            continue

        fvg_gap = abs(fvg_price - c[i]) / atrv

        sweep_found, sweep_strength = detect_liquidity_sweep(direction, h, l, c, i, SWING_LOOKBACK)
        if not sweep_found:
            continue

        atr_norm = atrv / c[i]
        rsi_m = (rsi_a[i] - 50.0) / 50.0
        bar_body = abs(c[i] - o[i])
        bar_size = bar_body / atrv

        if direction == 1:
            lower_wick = o[i] - l[i]
            wick_ratio = lower_wick / (bar_body + 1e-6)
            hl_rng = h[i] - l[i]
            close_pos = (c[i] - l[i]) / (hl_rng + 1e-6)
        else:
            upper_wick = h[i] - o[i]
            wick_ratio = upper_wick / (bar_body + 1e-6)
            hl_rng = h[i] - l[i]
            close_pos = (h[i] - c[i]) / (hl_rng + 1e-6)

        entry_price = c[i]
        fut = c[i + 1 : i + 21]
        if direction == 1:
            target = entry_price + 1.5 * atrv
            win = bool(np.any(fut > target))
        else:
            target = entry_price - 1.5 * atrv
            win = bool(np.any(fut < target))

        row = np.array(
            [
                ema_align,
                fvg_gap,
                sweep_strength,
                atr_norm,
                rsi_m,
                bar_size,
                wick_ratio,
                close_pos,
            ],
            dtype=np.float32,
        )

        features.append(row)
        labels.append(1 if win else 0)

    if not features:
        return None, None

    return np.array(features), np.array(labels)


def main():
    print("=" * 70)
    print("FVG Liquidity Sweep Filter — Multi-Timeframe XGBoost ONNX Training")
    print("=" * 70)
    print(f"Requested symbol: {SYMBOL}  |  Lookback: {TRAIN_MONTHS} month(s)  |  TFs: {', '.join(TF_NAMES)}")

    # Step 1: Connect and fetch
    data_path = connect_mt5()
    train_symbol = resolve_training_symbol(SYMBOL)
    print(f"Training on: {train_symbol}")
    if not train_symbol or mt5.symbol_info(train_symbol) is None:
        print("Abort: no valid symbol for training.")
        mt5.shutdown()
        sys.exit(1)

    files_dir = os.path.join(data_path, "MQL5", "Files")
    dfs = fetch_data_multitf(train_symbol)

    # Step 2: Build features from all timeframes
    print("\nBuilding feature matrix from all timeframes...")
    all_features = []
    all_labels = []

    for name, df in dfs.items():
        X, y = build_feature_matrix(df)
        if X is not None:
            all_features.append(X)
            all_labels.append(y)
            win_ratio = y.mean()
            print(f"[{name}] {len(X)} setups, {win_ratio:.1%} win rate")

    if not all_features:
        print("No valid features extracted!")
        mt5.shutdown()
        sys.exit(1)

    X = np.vstack(all_features)
    y = np.hstack(all_labels)

    print(f"\nTotal setups: {len(X)}")
    print(f"Win rate: {y.mean():.1%}")
    print(f"Loss rate: {(1-y.mean()):.1%}")

    # Step 3: Train/Test split (time-aware)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"\nTrain: {len(X_train)} setups ({y_train.mean():.1%} wins)")
    print(f"Test:  {len(X_test)} setups ({y_test.mean():.1%} wins)")

    # Step 4: Train XGBoost
    print("\n" + "=" * 70)
    print("Training XGBoost Binary Classifier")
    print("=" * 70)

    model = xgb.XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=40
    )

    # Step 5: Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = (y_pred == y_test).mean()
    if len(np.unique(y_test)) > 1:
        auc = roc_auc_score(y_test, y_proba)
    else:
        auc = float("nan")

    print(f"\nTest Accuracy: {acc:.4f}")
    print(f"Test AUC-ROC: {auc:.4f}" if not np.isnan(auc) else "\nTest AUC-ROC: n/a (single class in test set)")
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    if cm.size == 4:
        print(f"  TN: {cm[0,0]}, FP: {cm[0,1]}")
        print(f"  FN: {cm[1,0]}, TP: {cm[1,1]}")
    else:
        print(f"  (degenerate) {cm}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Loss", "Win"], labels=[0, 1], zero_division=0))

    # Feature importance
    print("Feature Importance:")
    feature_names = ["EMA_align", "FVG_gap", "Sweep_str", "ATR_norm",
                     "RSI_mom", "BarSize", "Wick_ratio", "Close_pos"]
    for name, imp in zip(feature_names, model.feature_importances_):
        print(f"  {name:12s}: {imp:.4f}")

    # Time-series CV (skip if too few samples)
    if len(X) >= 80:
        print("\nTime-Series Cross-Validation (5 folds):")
        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = []
        for fold, (tr_idx, te_idx) in enumerate(tscv.split(X)):
            m = xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.08,
                objective="binary:logistic", verbosity=0, random_state=42
            )
            m.fit(X[tr_idx], y[tr_idx])
            sc = (m.predict(X[te_idx]) == y[te_idx]).mean()
            cv_scores.append(sc)
            print(f"  Fold {fold+1}: {sc:.4f}")
        print(f"  Mean CV: {np.mean(cv_scores):.4f} +/- {np.std(cv_scores):.4f}")
    else:
        print(f"\nSkipping time-series CV (need more samples; have {len(X)}).")

    # Step 6: Export ONNX
    print("\n" + "=" * 70)
    print("Exporting ONNX Model")
    print("=" * 70)

    initial_type = [("features", FloatTensorType([1, N_FEATURES]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type,
                                  target_opset=ONNX_OPSET)

    output_path = os.path.join(files_dir, MODEL_NAME)
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Model saved: {output_path} ({size_kb:.1f} KB)")

    repo_copy = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_NAME)
    try:
        shutil.copy2(output_path, repo_copy)
        print(f"Copy for repo/workspace: {repo_copy}")
    except OSError as e:
        print(f"  (optional copy to repo folder failed: {e})")

    # Verify with ONNX Runtime (shape, dtypes, probabilities)
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])
        inp = sess.get_inputs()[0]
        outs = sess.get_outputs()
        print(f"  Input : {inp.name} shape={inp.shape} type={inp.type}")
        for o in outs:
            print(f"  Output: {o.name} shape={o.shape} type={o.type}")

        if inp.shape != [1, N_FEATURES] and list(inp.shape[-1:]) != [N_FEATURES]:
            print(f"  WARN: expected input last dim {N_FEATURES}, got {inp.shape}")

        z = np.zeros((1, N_FEATURES), dtype=np.float32)
        r0 = sess.run(None, {inp.name: z})
        test_vec = np.array([[1.0, 0.5, 1.0, 0.003, 0.1, 0.8, 1.2, 0.7]], dtype=np.float32)
        r1 = sess.run(None, {inp.name: test_vec})
        for tag, r in [("zeros", r0), ("sample", r1)]:
            probs = r[1] if len(r) > 1 else r[0]
            flat = np.asarray(probs).reshape(-1)
            if flat.size >= 2:
                s = float(flat[0] + flat[1])
                print(f"  Inference [{tag}]: class_probs[0:2]={flat[:2]}  sum={s:.4f}")
        print("  ONNX Runtime verification: OK")
    except Exception as e:
        print(f"  ONNX verification failed: {e}")

    mt5.shutdown()
    print(f"\n[OK] Training complete. Ready for FVG_LiquiditySweep_Sessions_EA_XGB.")
    print(f"  EA input: InpONNXPath = \"{MODEL_NAME}\"")
    print(f"  EA features: [{', '.join(feature_names)}]")


if __name__ == "__main__":
    main()
