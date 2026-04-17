"""
ML inference for EMA200 Squeeze model.
Loads the trained model (.pkl or .onnx) and runs predictions on live/new data.

Usage:
    python models/inference/predict.py --symbol GC=F
    python models/inference/predict.py --symbol AAPL --bars 20
"""

import argparse
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import yfinance as yf

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from models.feature_engineering.features import FEATURE_NAMES, build_features


def load_model(model_path: str = None):
    """Load model (pkl or onnx) and config."""
    saved_dir = os.path.join(PROJECT_ROOT, "models", "saved_models")

    if model_path is None:
        # Prefer ONNX, fallback to pkl
        onnx_path = os.path.join(saved_dir, "ema200_squeeze_model.onnx")
        pkl_path = os.path.join(saved_dir, "ema200_squeeze_model.pkl")
        if os.path.exists(onnx_path):
            model_path = onnx_path
        elif os.path.exists(pkl_path):
            model_path = pkl_path
        else:
            raise FileNotFoundError("No model found. Run training first.")

    config_path = os.path.join(saved_dir, "feature_config.json")
    with open(config_path) as f:
        config = json.load(f)

    if model_path.endswith(".onnx"):
        import onnxruntime as ort
        return {"type": "onnx", "session": ort.InferenceSession(model_path)}, config
    else:
        return {"type": "pkl", "model": joblib.load(model_path)}, config


def predict(model_info: dict, features: np.ndarray, threshold: float = 0.6) -> list[dict]:
    """Run prediction and return probabilities."""
    features = features.astype(np.float32)
    if features.ndim == 1:
        features = features.reshape(1, -1)

    if model_info["type"] == "onnx":
        session = model_info["session"]
        input_name = session.get_inputs()[0].name
        output_names = [o.name for o in session.get_outputs()]
        result = session.run(output_names, {input_name: features})
        probs = result[1]
        prob_buys = [float(p[1]) if not isinstance(p, dict) else float(p.get(1, 0)) for p in probs]
    else:
        model = model_info["model"]
        proba = model.predict_proba(features)
        prob_buys = proba[:, 1].tolist()

    predictions = []
    for prob_buy in prob_buys:
        prob_sell = 1.0 - prob_buy
        if prob_buy >= threshold:
            signal = "BUY"
        elif prob_sell >= threshold:
            signal = "SELL"
        else:
            signal = "NONE"

        predictions.append({
            "prob_buy": prob_buy,
            "prob_sell": prob_sell,
            "signal": signal,
            "confidence": max(prob_buy, prob_sell),
        })

    return predictions


def predict_live(symbol: str, n_bars: int = 20, model_path: str = None):
    """Download latest data, compute features, and predict."""
    print(f"\nPredicting for {symbol}...")

    model_info, config = load_model(model_path)
    threshold = config.get("threshold", 0.6)
    model_type = model_info["type"].upper()
    print(f"Model type: {model_type}")

    # Download recent data (need 250+ bars for EMA200 warmup)
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="60d", interval="1h")

    if df.empty:
        print(f"No data for {symbol}")
        return None

    print(f"Downloaded {len(df)} bars")

    # Build features
    df = build_features(df)
    df = df.dropna(subset=FEATURE_NAMES)

    if len(df) == 0:
        print("Not enough data after feature computation")
        return None

    # Get last N bars
    df_recent = df.tail(n_bars)
    X = df_recent[FEATURE_NAMES].values.astype(np.float32)

    # Predict
    predictions = predict(model_info, X, threshold)

    # Display results
    print(f"\nLast {min(n_bars, len(predictions))} predictions (threshold={threshold}):")
    print(f"{'DateTime':>20s}  {'Close':>10s}  {'Buy%':>6s}  {'Sell%':>6s}  {'Signal':>6s}  {'EMA Touch':>9s}")
    print("-" * 70)

    for i in range(len(predictions)):
        idx = df_recent.index[i]
        close = df_recent.iloc[i]["Close"]
        pred = predictions[i]
        touch = "YES" if df_recent.iloc[i]["ema_touch"] == 1 else "no"
        dt_str = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)
        print(f"{dt_str:>20s}  {close:>10.2f}  {pred['prob_buy']:>5.1%}  {pred['prob_sell']:>5.1%}  {pred['signal']:>6s}  {touch:>9s}")

    # Current signal
    latest = predictions[-1]
    print(f"\nCurrent Signal: {latest['signal']} (Buy: {latest['prob_buy']:.1%}, Sell: {latest['prob_sell']:.1%})")

    return predictions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EMA200 Squeeze ML Prediction")
    parser.add_argument("--symbol", default="GC=F", help="Yahoo Finance symbol")
    parser.add_argument("--bars", type=int, default=10, help="Number of recent bars to show")
    parser.add_argument("--model", default=None, help="Path to ONNX model file")

    args = parser.parse_args()
    predict_live(args.symbol, n_bars=args.bars, model_path=args.model)
