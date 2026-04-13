"""
Gold Regime XGBoost ONNX Training Pipeline
-------------------------------------------
Connects to MetaTrader 5, pulls XAUUSD H1 data, detects Bull/Bear/Chop
regimes via Gaussian Mixture Model, trains XGBoost classifier on 4 features
matching the EA (HMM state proxy, RSI delta, normalized ATR, log return),
and exports to ONNX format for the GoldRegime_ONNX_XGB_EA.

Output: GoldRegimeX.onnx -> MQL5/Files/
"""

import sys
import os
import datetime
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

from sklearn.mixture import GaussianMixture
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import RobustScaler

import xgboost as xgb
import onnxmltools
from onnxmltools.convert import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType


# ─── CONFIG ──────────────────────────────────────────────────────────
SYMBOL       = "XAUUSD"
TIMEFRAME    = mt5.TIMEFRAME_H1
BARS         = 30000          # ~3.5 years of H1 data
RSI_PERIOD   = 14
ATR_PERIOD   = 14
N_REGIMES    = 3              # Bull, Bear, Chop
TEST_RATIO   = 0.2
ONNX_OPSET   = 15
MODEL_NAME   = "GoldRegimeX.onnx"


def connect_mt5():
    """Initialize MT5 connection."""
    if not mt5.initialize():
        print(f"MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    info = mt5.terminal_info()
    print(f"Connected to MT5: {info.path}")
    return info.data_path


def fetch_data(symbol, timeframe, bars):
    """Pull OHLCV from MT5."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        print(f"No data for {symbol}")
        sys.exit(1)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    print(f"Fetched {len(df)} bars: {df.index[0]} to {df.index[-1]}")
    return df


def compute_rsi(series, period=14):
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_atr(df, period=14):
    """Average True Range using Wilder's smoothing."""
    high  = df["high"]
    low   = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def build_features(df):
    """
    Build the 4 features matching the EA exactly:
      0: HMM state proxy  (1=up, 0=down, 0.5=flat based on log return sign)
      1: RSI delta         (RSI[t] - RSI[t-1])
      2: Normalized ATR    (ATR / close)
      3: Log return        (ln(close[t] / close[t-1]))
    """
    df = df.copy()
    df["log_return"]   = np.log(df["close"] / df["close"].shift(1))
    df["hmm_state"]    = np.where(df["log_return"] > 0, 1.0,
                          np.where(df["log_return"] < 0, 0.0, 0.5))
    df["rsi"]          = compute_rsi(df["close"], RSI_PERIOD)
    df["rsi_delta"]    = df["rsi"].diff()
    df["atr"]          = compute_atr(df, ATR_PERIOD)
    df["atr_norm"]     = df["atr"] / df["close"]
    df.dropna(inplace=True)
    return df


def label_regimes(df):
    """
    Use Gaussian Mixture Model on rolling returns to detect 3 regimes.
    Then label them as Bull (highest mean), Bear (lowest mean), Chop (middle).
    """
    # Use 20-bar rolling return + volatility for clustering
    df = df.copy()
    df["roll_ret"]  = df["log_return"].rolling(20).mean()
    df["roll_vol"]  = df["log_return"].rolling(20).std()
    df.dropna(inplace=True)

    X_cluster = df[["roll_ret", "roll_vol"]].values
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_cluster)

    gmm = GaussianMixture(n_components=N_REGIMES, covariance_type="full",
                           n_init=10, random_state=42)
    gmm.fit(X_scaled)
    labels = gmm.predict(X_scaled)
    df["regime"] = labels

    # Sort clusters by mean return to assign semantic labels
    cluster_means = {}
    for c in range(N_REGIMES):
        mask = labels == c
        cluster_means[c] = df["roll_ret"].values[mask].mean()

    sorted_clusters = sorted(cluster_means, key=cluster_means.get)
    # sorted_clusters[0] = Bear (lowest), [1] = Chop, [2] = Bull (highest)
    label_map = {
        sorted_clusters[0]: 1,  # Bear
        sorted_clusters[1]: 2,  # Chop
        sorted_clusters[2]: 0,  # Bull
    }
    df["regime"] = df["regime"].map(label_map)

    # Print regime distribution
    counts = df["regime"].value_counts().sort_index()
    names = {0: "Bull", 1: "Bear", 2: "Chop"}
    print("\nRegime distribution:")
    for idx, cnt in counts.items():
        pct = cnt / len(df) * 100
        print(f"  {names[idx]:5s}: {cnt:6d} bars ({pct:.1f}%)")

    return df


def train_xgboost(df):
    """
    Train XGBoost multi-class classifier (3 classes: Bull=0, Bear=1, Chop=2).
    Uses time-series aware split to prevent look-ahead bias.
    """
    feature_cols = ["hmm_state", "rsi_delta", "atr_norm", "log_return"]
    X = df[feature_cols].values.astype(np.float32)
    y = df["regime"].values.astype(int)

    # Time-series split: last TEST_RATIO for testing
    split_idx = int(len(X) * (1 - TEST_RATIO))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"\nTraining: {len(X_train)} bars, Testing: {len(X_test)} bars")

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50
    )

    # Evaluate
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nTest Accuracy: {acc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred,
          target_names=["Bull", "Bear", "Chop"]))

    # Feature importance
    print("Feature Importance:")
    for name, imp in zip(feature_cols, model.feature_importances_):
        print(f"  {name:15s}: {imp:.4f}")

    # Time-series cross-validation
    print("\nTime-Series CV (5 folds):")
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = []
    for fold, (tr_idx, te_idx) in enumerate(tscv.split(X)):
        m = xgb.XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            objective="multi:softprob", num_class=3,
            use_label_encoder=False, verbosity=0, random_state=42
        )
        m.fit(X[tr_idx], y[tr_idx])
        sc = accuracy_score(y[te_idx], m.predict(X[te_idx]))
        cv_scores.append(sc)
        print(f"  Fold {fold+1}: {sc:.4f}")
    print(f"  Mean CV: {np.mean(cv_scores):.4f} ± {np.std(cv_scores):.4f}")

    return model


def export_onnx(model, output_path):
    """
    Export XGBoost model to ONNX.
    Input shape: [1, 4] (4 features as float32)
    Output: probabilities for [Bull, Bear, Chop]
    """
    initial_type = [("features", FloatTensorType([1, 4]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type,
                                  target_opset=ONNX_OPSET)

    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nONNX model saved: {output_path} ({size_kb:.1f} KB)")

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
        test_features = np.array([[1.0, 2.5, 0.005, 0.001]], dtype=np.float32)
        result = sess.run(None, {inp.name: test_features})
        # XGBoost ONNX outputs: [0] = labels, [1] = probabilities
        if len(result) > 1:
            probs = result[1]
            print(f"  Test inference OK. Probs: {probs}")
        else:
            print(f"  Test inference OK. Output: {result[0]}")
    except Exception as e:
        print(f"  ONNX verification warning: {e}")


def main():
    print("=" * 60)
    print("Gold Regime XGBoost — ONNX Training Pipeline")
    print("=" * 60)

    # Step 1: Connect and fetch data
    data_path = connect_mt5()
    files_dir = os.path.join(data_path, "MQL5", "Files")
    df = fetch_data(SYMBOL, TIMEFRAME, BARS)

    # Step 2: Build features
    print("\nBuilding features...")
    df = build_features(df)
    print(f"Feature matrix: {len(df)} rows x 4 features")

    # Step 3: Label regimes via GMM
    print("\nDetecting regimes via Gaussian Mixture Model...")
    df = label_regimes(df)

    # Step 4: Train XGBoost
    print("\n" + "=" * 60)
    print("Training XGBoost Classifier")
    print("=" * 60)
    model = train_xgboost(df)

    # Step 5: Export ONNX
    output_path = os.path.join(files_dir, MODEL_NAME)
    export_onnx(model, output_path)

    mt5.shutdown()
    print("\n[OK] Done. Model ready for GoldRegime_ONNX_XGB_EA.")
    print(f"  EA input param InpONNXPath = \"{MODEL_NAME}\"")


if __name__ == "__main__":
    main()
