"""
FVG Liquidity Sweep Filter — Multi-Timeframe XGBoost ONNX
----------------------------------------------------------
Trains XGBoost classifier to filter winning vs losing FVG+sweep setups
across M1, M5, M15, M30, H1 timeframes. Binary classification (1=win, 0=loss).

Features extracted from price action around FVG detection:
  - EMA alignment score (9/21/50 stack quality)
  - Liquidity sweep strength (wick extension beyond swing)
  - FVG gap size (normalized by ATR)
  - ATR volatility
  - RSI momentum
  - Volume profile
  - MTF bias (H4/D1 trend alignment)

Output: FVG_Filter_XGB.onnx -> MQL5/Files/
"""

import sys
import os
import datetime
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb
from onnxmltools.convert.common.data_types import FloatTensorType
from onnxmltools.convert import convert_xgboost


# ─── CONFIG ──────────────────────────────────────────────────────────
SYMBOL       = "XAUUSD"
TIMEFRAMES   = [mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15,
                mt5.TIMEFRAME_M30, mt5.TIMEFRAME_H1]
TF_NAMES     = ["M1", "M5", "M15", "M30", "H1"]
BARS_PER_TF  = 20000
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


def fetch_data_multitf():
    """Fetch OHLCV data for all timeframes."""
    data = {}
    for tf, name in zip(TIMEFRAMES, TF_NAMES):
        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, BARS_PER_TF)
        if rates is None or len(rates) == 0:
            print(f"No data for {name}")
            continue
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


def detect_fvg_bullish(highs, lows, i, min_gap):
    """Check for bullish FVG at bar i: lows[i] > highs[i+2]"""
    if i < 2:
        return False, 0.0
    gap = lows.iloc[i] - highs.iloc[i+2] if i+2 < len(highs) else 0
    if gap > min_gap:
        return True, (lows.iloc[i] + highs.iloc[i+2]) / 2.0
    return False, 0.0


def detect_fvg_bearish(highs, lows, i, min_gap):
    """Check for bearish FVG at bar i: highs[i] < lows[i+2]"""
    if i < 2:
        return False, 0.0
    gap = lows.iloc[i+2] - highs.iloc[i] if i+2 < len(highs) else 0
    if gap > min_gap:
        return True, (highs.iloc[i] + lows.iloc[i+2]) / 2.0
    return False, 0.0


def detect_liquidity_sweep(direction, highs, lows, closes, i, lookback=20):
    """Detect swing high/low sweep. Returns (detected, sweep_strength)"""
    if i < lookback + 2:
        # Relaxed: check in available lookback
        lookback = min(i - 2, lookback)

    subset_high = highs.iloc[max(0, i-lookback):i]
    subset_low = lows.iloc[max(0, i-lookback):i]

    if direction == 1:  # Bullish: looking for swept swing low
        swing_low = subset_low.min()
        if lows.iloc[i-1] <= swing_low:  # Relaxed: wick touches
            strength = max(0.5, (closes.iloc[i-1] - lows.iloc[i-1]) / (closes.iloc[i-1] - swing_low + 1e-6))
            return True, min(strength, 2.0)
    else:  # Bearish: looking for swept swing high
        swing_high = subset_high.max()
        if highs.iloc[i-1] >= swing_high:  # Relaxed: wick touches
            strength = max(0.5, (highs.iloc[i-1] - closes.iloc[i-1]) / (swing_high - closes.iloc[i-1] + 1e-6))
            return True, min(strength, 2.0)

    return False, 0.0


def build_feature_matrix(df):
    """Extract 8 features for each bar."""
    df = df.copy()
    n = len(df)

    # Indicators
    df["ema_fast"] = compute_ema(df["close"], EMA_FAST)
    df["ema_slow"] = compute_ema(df["close"], EMA_SLOW)
    df["ema_trend"] = compute_ema(df["close"], EMA_TREND)
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df.dropna(inplace=True)

    features = []
    labels = []

    min_gap_baseline = df["atr"].median() * 0.1  # Relaxed threshold

    for i in range(FVG_LOOKBACK, len(df) - 20):
        atr = df["atr"].iloc[i]
        if atr <= 0:
            continue

        # Feature 1: EMA alignment (bullish=1, bearish=-1, choppy=0)
        ema_fast = df["ema_fast"].iloc[i]
        ema_slow = df["ema_slow"].iloc[i]
        ema_trend = df["ema_trend"].iloc[i]

        if ema_fast > ema_slow > ema_trend:
            ema_align = 1.0
            direction = 1  # Bullish setup
        elif ema_fast < ema_slow < ema_trend:
            ema_align = -1.0
            direction = -1  # Bearish setup
        else:
            ema_align = 0.0
            direction = 0

        if direction == 0:
            continue

        # Feature 2: FVG detection and gap size
        if direction == 1:
            fvg_found, fvg_price = detect_fvg_bullish(df["high"], df["low"], i, min_gap_baseline)
        else:
            fvg_found, fvg_price = detect_fvg_bearish(df["high"], df["low"], i, min_gap_baseline)

        if not fvg_found:
            continue

        fvg_gap = abs(fvg_price - df["close"].iloc[i]) / atr

        # Feature 3: Liquidity sweep detection
        sweep_found, sweep_strength = detect_liquidity_sweep(direction, df["high"],
                                                               df["low"], df["close"], i, SWING_LOOKBACK)
        if not sweep_found:
            continue

        # Feature 4: ATR normalized
        atr_norm = atr / df["close"].iloc[i]

        # Feature 5: RSI momentum
        rsi = df["rsi"].iloc[i]
        rsi_momentum = (rsi - 50) / 50.0

        # Feature 6: Bar size (body / ATR)
        bar_body = abs(df["close"].iloc[i] - df["open"].iloc[i])
        bar_size = bar_body / atr

        # Feature 7: Wick extension
        if direction == 1:
            lower_wick = df["open"].iloc[i] - df["low"].iloc[i]
            wick_ratio = lower_wick / (bar_body + 1e-6)
        else:
            upper_wick = df["high"].iloc[i] - df["open"].iloc[i]
            wick_ratio = upper_wick / (bar_body + 1e-6)

        # Feature 8: Close proximity to extreme
        if direction == 1:
            close_pos = (df["close"].iloc[i] - df["low"].iloc[i]) / (df["high"].iloc[i] - df["low"].iloc[i] + 1e-6)
        else:
            close_pos = (df["high"].iloc[i] - df["close"].iloc[i]) / (df["high"].iloc[i] - df["low"].iloc[i] + 1e-6)

        # Label: winning setup (direction confirmation in next 20 bars)
        # Bullish win: price closes above entry + 1.5*atr within 20 bars
        # Bearish win: price closes below entry - 1.5*atr within 20 bars
        entry_price = df["close"].iloc[i]
        future_closes = df["close"].iloc[i+1:min(i+21, len(df))]

        if direction == 1:
            target = entry_price + 1.5 * atr
            win = (future_closes > target).any()
        else:
            target = entry_price - 1.5 * atr
            win = (future_closes < target).any()

        row = np.array([
            ema_align,           # 0: EMA alignment
            fvg_gap,             # 1: FVG gap normalized
            sweep_strength,      # 2: Liquidity sweep strength
            atr_norm,            # 3: ATR ratio
            rsi_momentum,        # 4: RSI momentum
            bar_size,            # 5: Bar body size
            wick_ratio,          # 6: Wick extension
            close_pos            # 7: Close position
        ], dtype=np.float32)

        features.append(row)
        labels.append(1 if win else 0)

    if not features:
        return None, None

    return np.array(features), np.array(labels)


def main():
    print("=" * 70)
    print("FVG Liquidity Sweep Filter — Multi-Timeframe XGBoost ONNX Training")
    print("=" * 70)

    # Step 1: Connect and fetch
    data_path = connect_mt5()
    files_dir = os.path.join(data_path, "MQL5", "Files")
    dfs = fetch_data_multitf()

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
    auc = roc_auc_score(y_test, y_proba)

    print(f"\nTest Accuracy: {acc:.4f}")
    print(f"Test AUC-ROC: {auc:.4f}")
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  TN: {cm[0,0]}, FP: {cm[0,1]}")
    print(f"  FN: {cm[1,0]}, TP: {cm[1,1]}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Loss", "Win"]))

    # Feature importance
    print("Feature Importance:")
    feature_names = ["EMA_align", "FVG_gap", "Sweep_str", "ATR_norm",
                     "RSI_mom", "BarSize", "Wick_ratio", "Close_pos"]
    for name, imp in zip(feature_names, model.feature_importances_):
        print(f"  {name:12s}: {imp:.4f}")

    # Time-series CV
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

    # Verify with ONNX Runtime
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(output_path)
        inp = sess.get_inputs()[0]
        out = sess.get_outputs()
        print(f"  Input : {inp.name} {inp.shape} {inp.type}")
        for o in out:
            print(f"  Output: {o.name} {o.shape} {o.type}")

        # Test inference
        test_features = np.array([[1.0, 0.5, 1.0, 0.003, 0.1, 0.8, 1.2, 0.7]], dtype=np.float32)
        result = sess.run(None, {inp.name: test_features})
        print(f"  Test inference OK. Output: {result[1]}")
    except Exception as e:
        print(f"  ONNX verification: {e}")

    mt5.shutdown()
    print(f"\n[OK] Training complete. Ready for FVG_LiquiditySweep_Sessions_EA_XGB.")
    print(f"  EA input: InpONNXPath = \"{MODEL_NAME}\"")
    print(f"  EA features: [{', '.join(feature_names)}]")


if __name__ == "__main__":
    main()
