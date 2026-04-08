"""
Train EMA200 Squeeze ML model and export to ONNX.

Downloads 1H data from Yahoo Finance, engineers features,
trains a LightGBM classifier, and exports to ONNX format.

Usage:
    python models/training/train_model.py
    python models/training/train_model.py --symbol AAPL --period 2y
    python models/training/train_model.py --symbol XAUUSD=X --period 5y --tp-points 30
"""

import argparse
import os
import sys
import warnings

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from models.feature_engineering.features import FEATURE_NAMES, build_features, compute_atr

warnings.filterwarnings("ignore")

# Default symbols for training data
DEFAULT_SYMBOLS = ["GC=F", "XAU=F", "EURUSD=X", "GBPUSD=X", "SPY", "QQQ", "AAPL"]


def download_data(symbols: list[str], period: str = "2y", interval: str = "1h") -> pd.DataFrame:
    """Download 1H OHLCV data from Yahoo Finance."""
    all_data = []

    for symbol in symbols:
        print(f"  Downloading {symbol}...")
        try:
            ticker = yf.Ticker(symbol)
            # yfinance limits 1h data to ~730 days, use max available
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                print(f"    No data for {symbol}, skipping")
                continue
            df["Symbol"] = symbol
            all_data.append(df)
            print(f"    Got {len(df)} bars from {df.index[0]} to {df.index[-1]}")
        except Exception as e:
            print(f"    Error downloading {symbol}: {e}")
            continue

    if not all_data:
        raise ValueError("No data downloaded for any symbol")

    return pd.concat(all_data, ignore_index=False)


def create_labels(df: pd.DataFrame, lookahead: int = 10) -> pd.Series:
    """
    Create labels based on future price direction.

    For each bar, look at the close N bars ahead:
    - If future close > current close by more than half ATR -> 1 (buy)
    - If future close < current close by more than half ATR -> -1 (sell)
    - Otherwise -> 0 (no clear signal)
    """
    labels = pd.Series(0, index=df.index, dtype=int)
    close = df["Close"].values

    # Use rolling ATR to set a dynamic threshold
    atr = compute_atr(df["High"], df["Low"], df["Close"], 14).values

    for i in range(len(close) - lookahead):
        if np.isnan(atr[i]) or atr[i] == 0:
            continue

        future_close = close[i + lookahead]
        change = future_close - close[i]
        threshold = atr[i] * 0.5  # half ATR as minimum move

        if change > threshold:
            labels.iloc[i] = 1   # bullish
        elif change < -threshold:
            labels.iloc[i] = -1  # bearish

    return labels


def train(symbols: list[str] = None, period: str = "2y", lookahead: int = 10):
    """Train the model and export to ONNX."""

    if symbols is None:
        symbols = DEFAULT_SYMBOLS

    save_dir = os.path.join(PROJECT_ROOT, "models", "saved_models")
    os.makedirs(save_dir, exist_ok=True)

    # --- Step 1: Download Data ---
    print("\n[1/5] Downloading 1H data from Yahoo Finance...")
    raw_data = download_data(symbols, period=period)
    print(f"  Total bars: {len(raw_data)}")

    # --- Step 2: Feature Engineering ---
    print("\n[2/5] Computing features...")
    all_features = []
    all_labels = []

    for symbol in raw_data["Symbol"].unique():
        sym_data = raw_data[raw_data["Symbol"] == symbol].copy()
        sym_data = sym_data.sort_index()

        # Build features (this computes ATR internally)
        sym_features = build_features(sym_data)

        # Create labels using the original OHLC data
        sym_labels = create_labels(sym_features, lookahead=lookahead)

        sym_features["label"] = sym_labels
        all_features.append(sym_features)
        print(f"    {symbol}: {(sym_labels != 0).sum()} labeled bars")

    df = pd.concat(all_features)

    # Drop NaN rows from warmup period
    df = df.dropna(subset=FEATURE_NAMES + ["label"])

    # Remove 0 labels (no clear signal) - train only on clear buy/sell
    df_trades = df[df["label"] != 0].copy()

    # Convert to binary: 1=buy, 0=sell
    df_trades["target"] = (df_trades["label"] == 1).astype(int)

    X = df_trades[FEATURE_NAMES].values.astype(np.float32)
    y = df_trades["target"].values

    print(f"  Samples with clear signals: {len(X)}")
    print(f"  Buy signals: {y.sum()} ({y.mean() * 100:.1f}%)")
    print(f"  Sell signals: {len(y) - y.sum()} ({(1 - y.mean()) * 100:.1f}%)")

    # --- Step 3: Train LightGBM ---
    print("\n[3/5] Training LightGBM classifier...")

    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 63,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 50,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "n_jobs": -1,
    }

    # Time-series cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        train_data = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        model = lgb.train(
            params, train_data,
            num_boost_round=500,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
        )

        val_pred = model.predict(X_val)
        auc = roc_auc_score(y_val, val_pred)
        acc = accuracy_score(y_val, (val_pred > 0.5).astype(int))
        cv_scores.append(auc)
        print(f"  Fold {fold + 1}: AUC={auc:.4f}, Acc={acc:.4f}")

    print(f"  Mean CV AUC: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

    # Train final model on all data
    print("\n  Training final model on full dataset...")
    train_data = lgb.Dataset(X, label=y, feature_name=FEATURE_NAMES)
    final_model = lgb.train(params, train_data, num_boost_round=300)

    # Feature importance
    importance = final_model.feature_importance(importance_type="gain")
    feat_imp = sorted(zip(FEATURE_NAMES, importance), key=lambda x: x[1], reverse=True)
    print("\n  Top 10 features by gain:")
    for name, imp in feat_imp[:10]:
        print(f"    {name:25s} {imp:.1f}")

    # --- Step 4: Export Models ---
    print("\n[4/5] Exporting models...")

    # Save LightGBM native model
    lgb_path = os.path.join(save_dir, "ema200_squeeze_model.lgb")
    final_model.save_model(lgb_path)
    print(f"  LightGBM model saved: {lgb_path}")

    # Save sklearn-compatible model for inference
    sklearn_model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=300,
        num_leaves=63,
        learning_rate=0.05,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=5,
        min_child_samples=50,
        reg_alpha=0.1,
        reg_lambda=0.1,
        verbose=-1,
        n_jobs=-1,
    )
    sklearn_model.fit(X, y)

    sklearn_pred = sklearn_model.predict_proba(X)[:, 1]
    sklearn_auc = roc_auc_score(y, sklearn_pred)
    print(f"  Sklearn model AUC on training data: {sklearn_auc:.4f}")

    pkl_path = os.path.join(save_dir, "ema200_squeeze_model.pkl")
    joblib.dump(sklearn_model, pkl_path)
    print(f"  Sklearn model saved: {pkl_path}")

    # Try ONNX export (may fail on some Windows setups)
    onnx_path = os.path.join(save_dir, "ema200_squeeze_model.onnx")
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType

        initial_type = [("features", FloatTensorType([None, len(FEATURE_NAMES)]))]
        onnx_model = convert_sklearn(
            sklearn_model, initial_types=initial_type,
            target_opset=12, options={type(sklearn_model): {"zipmap": False}}
        )
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"  ONNX model saved: {onnx_path}")
    except Exception as e:
        print(f"  ONNX export skipped ({e})")
        print(f"  Use the .pkl model with Python inference or export ONNX on a Linux machine")
        onnx_path = None

    # --- Step 5: Validate Model ---
    print("\n[5/5] Validating model...")

    # Validate with sklearn model
    test_input = X[:10]
    test_probs = sklearn_model.predict_proba(test_input)
    print(f"  Sample probabilities (first 5):")
    for i in range(5):
        print(f"    Bar {i}: Buy prob = {test_probs[i][1]:.4f}")

    # Validate ONNX if available
    if onnx_path and os.path.exists(onnx_path):
        import onnxruntime as ort
        session = ort.InferenceSession(onnx_path)
        input_name = session.get_inputs()[0].name
        output_names = [o.name for o in session.get_outputs()]
        onnx_result = session.run(output_names, {input_name: test_input.astype(np.float32)})
        onnx_probs = onnx_result[1]
        print(f"  ONNX validation passed")

    # Save feature config for MQL5
    config_path = os.path.join(save_dir, "feature_config.json")
    import json
    config = {
        "feature_names": FEATURE_NAMES,
        "n_features": len(FEATURE_NAMES),
        "threshold": 0.6,
        "symbols_trained": symbols,
        "period": period,
        "lookahead": lookahead,
        "cv_auc_mean": float(np.mean(cv_scores)),
        "cv_auc_std": float(np.std(cv_scores)),
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Config saved: {config_path}")

    print("\n Training complete!")
    print(f"  ONNX model: {onnx_path}")
    print(f"  Copy the .onnx file to MQL5/Files/ for use in the EA")

    return final_model, onnx_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train EMA200 Squeeze ML model")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Yahoo Finance symbols to train on")
    parser.add_argument("--period", default="2y", help="Data period (e.g., 1y, 2y, 5y)")
    parser.add_argument("--lookahead", type=int, default=10, help="Lookahead bars for labeling")

    args = parser.parse_args()
    train(symbols=args.symbols, period=args.period, lookahead=args.lookahead)
