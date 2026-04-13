"""
Gold Regime Detection — HMM + XGBoost Pipeline
1. Kalman-smoothed log returns + rolling volatility
2. Gaussian HMM classifies Bull/Bear/Chop market regimes
3. Volatility-bucketed XGBoost ensemble predicts next-bar direction
4. Signal: BUY if bull_prob > threshold AND Bull regime
           SELL if bear_prob > threshold AND Bear regime
           HOLD in Chop regime
ATR-based position sizing and stop losses.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from typing import Optional, Tuple, Dict
import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    log.warning("hmmlearn not installed. Using simple regime detection fallback.")

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    log.warning("xgboost not installed. Using logistic regression fallback.")


def kalman_smooth(series: pd.Series, obs_cov: float = 0.5) -> pd.Series:
    """Simple 1D Kalman filter for return smoothing."""
    n = len(series)
    x = np.zeros(n)
    p = np.ones(n)
    q = 0.01   # Process noise
    r = obs_cov  # Observation noise

    x[0] = series.iloc[0]
    p[0] = 1.0

    for i in range(1, n):
        # Predict
        x_pred = x[i - 1]
        p_pred = p[i - 1] + q
        # Update
        k = p_pred / (p_pred + r)
        x[i] = x_pred + k * (series.iloc[i] - x_pred)
        p[i] = (1 - k) * p_pred

    return pd.Series(x, index=series.index)


def compute_features(df: pd.DataFrame, obs_cov: float = 0.5) -> pd.DataFrame:
    """Feature engineering: Kalman returns, volatility, RSI, ATR."""
    close = df["close"]

    # Log returns
    log_return = np.log(close / close.shift(1))

    # Kalman-smoothed returns
    kalman_return = kalman_smooth(log_return.fillna(0), obs_cov)

    # Rolling volatility (20-period)
    volatility = log_return.rolling(20).std()

    # RSI(14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi_slope = rsi.diff()

    # ATR(14) normalized
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - close.shift(1)).abs(),
        (df["low"] - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_normalized = atr / close

    features = pd.DataFrame({
        "kalman_return": kalman_return,
        "volatility": volatility,
        "rsi_slope": rsi_slope,
        "atr_normalized": atr_normalized,
        "log_return": log_return,
    }, index=df.index)

    return features.dropna()


def train_hmm(features: pd.DataFrame, n_states: int = 3) -> Tuple:
    """Train Gaussian HMM on returns + volatility."""
    X = features[["kalman_return", "volatility"]].values

    if not HMM_AVAILABLE:
        # Fallback: simple threshold-based regime
        log.info("Using threshold-based regime detection (no HMM)")
        return None, None

    model = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=200,
        random_state=42,
    )
    model.fit(X)
    states = model.predict(X)

    # Sort states by mean return: 0=Bear, 1=Chop, 2=Bull
    means = [features["kalman_return"].values[states == s].mean() for s in range(n_states)]
    sorted_states = np.argsort(means)
    state_map = {sorted_states[0]: "Bear", sorted_states[1]: "Chop", sorted_states[2]: "Bull"}

    log.info(f"HMM trained. State map: {state_map}")
    for s in range(n_states):
        label = state_map.get(s, "?")
        persistence = (model.transmat_[s, s] * 100)
        log.info(f"  State {s} ({label}): mean_ret={means[s]:.5f} persistence={persistence:.1f}%")

    return model, state_map


def get_regime(model, state_map, features: pd.DataFrame) -> pd.Series:
    """Predict regime for each bar."""
    if model is None:
        # Fallback: volatility + return based
        regimes = pd.Series("Chop", index=features.index)
        ret = features["kalman_return"]
        vol = features["volatility"]
        vol_median = vol.median()
        regimes[ret > 0.001] = "Bull"
        regimes[ret < -0.001] = "Bear"
        regimes[vol > vol_median * 1.5] = "Chop"
        return regimes

    X = features[["kalman_return", "volatility"]].values
    states = model.predict(X)
    return pd.Series([state_map.get(s, "Chop") for s in states], index=features.index)


def train_xgboost_ensemble(features: pd.DataFrame, regimes: pd.Series) -> Dict:
    """Train volatility-bucketed XGBoost classifiers."""
    # Binary target: next bar return > 0
    target = (features["log_return"].shift(-1) > 0).astype(int)
    data = features.copy()
    data["regime"] = regimes
    data["target"] = target
    data = data.dropna()

    # Split by ATR buckets
    atr = data["atr_normalized"]
    q33 = atr.quantile(0.33)
    q66 = atr.quantile(0.66)

    buckets = {
        "low": data[atr <= q33],
        "med": data[(atr > q33) & (atr <= q66)],
        "high": data[atr > q66],
    }

    feat_cols = ["kalman_return", "volatility", "rsi_slope", "atr_normalized", "log_return"]
    models = {}

    for bucket_name, bucket_data in buckets.items():
        if len(bucket_data) < 50:
            continue

        X = bucket_data[feat_cols].values
        y = bucket_data["target"].values

        # Temporal split (80/20)
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        if XGB_AVAILABLE:
            clf = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                reg_alpha=0.1,
                reg_lambda=1.0,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )
        else:
            from sklearn.linear_model import LogisticRegression
            clf = LogisticRegression(max_iter=1000)

        clf.fit(X_train, y_train)
        acc = clf.score(X_test, y_test)
        log.info(f"  {bucket_name} bucket: train={len(X_train)} test={len(X_test)} acc={acc:.3f}")
        models[bucket_name] = clf

    return models


def predict_signal(models: Dict, features_row: pd.Series, regime: str,
                   threshold: float = 0.65) -> Tuple[str, float]:
    """Generate trading signal from ensemble."""
    if regime == "Chop":
        return "HOLD", 0.5

    feat_cols = ["kalman_return", "volatility", "rsi_slope", "atr_normalized", "log_return"]
    X = features_row[feat_cols].values.reshape(1, -1)

    # Select model by ATR bucket
    atr = features_row["atr_normalized"]
    if atr <= 0.005:
        bucket = "low"
    elif atr <= 0.01:
        bucket = "med"
    else:
        bucket = "high"

    model = models.get(bucket)
    if model is None:
        model = models.get("med") or next(iter(models.values()), None)
    if model is None:
        return "HOLD", 0.5

    prob = model.predict_proba(X)[0]
    bull_prob = prob[1]

    if bull_prob > threshold and regime == "Bull":
        return "BUY", bull_prob
    elif bull_prob < (1 - threshold) and regime == "Bear":
        return "SELL", 1 - bull_prob
    return "HOLD", max(bull_prob, 1 - bull_prob)


def backtest(df: pd.DataFrame, threshold: float = 0.65, risk_pct: float = 0.01,
             obs_cov: float = 0.5) -> pd.DataFrame:
    """Full pipeline backtest."""
    log.info(f"Computing features (obs_cov={obs_cov})...")
    features = compute_features(df, obs_cov)

    log.info("Training HMM...")
    hmm_model, state_map = train_hmm(features)

    log.info("Predicting regimes...")
    regimes = get_regime(hmm_model, state_map, features)

    log.info("Training XGBoost ensemble...")
    xgb_models = train_xgboost_ensemble(features, regimes)

    # Walk-forward signals
    results = []
    for i in range(int(len(features) * 0.8), len(features)):
        row = features.iloc[i]
        regime = regimes.iloc[i]
        signal, confidence = predict_signal(xgb_models, row, regime, threshold)

        future_ret = features["log_return"].iloc[i + 1] if i + 1 < len(features) else 0
        atr_stop = row["atr_normalized"] * 2.0

        pnl = 0
        if signal == "BUY":
            pnl = min(future_ret, atr_stop * 1.5) if future_ret > 0 else max(future_ret, -atr_stop)
        elif signal == "SELL":
            pnl = min(-future_ret, atr_stop * 1.5) if future_ret < 0 else max(-future_ret, -atr_stop)

        results.append({
            "time": features.index[i] if isinstance(features.index, pd.DatetimeIndex) else i,
            "regime": regime,
            "signal": signal,
            "confidence": confidence,
            "pnl": pnl * risk_pct,
        })

    results_df = pd.DataFrame(results)

    # Statistics
    trades = results_df[results_df["signal"] != "HOLD"]
    if len(trades) > 0:
        wins = trades[trades["pnl"] > 0]
        cum_pnl = trades["pnl"].sum()
        sharpe = trades["pnl"].mean() / trades["pnl"].std() * np.sqrt(252) if trades["pnl"].std() > 0 else 0
        max_dd = (trades["pnl"].cumsum().cummax() - trades["pnl"].cumsum()).max()

        log.info(f"\n=== Results ===")
        log.info(f"Total signals: {len(trades)} | Wins: {len(wins)} | Win rate: {len(wins)/len(trades)*100:.1f}%")
        log.info(f"Cumulative PnL: {cum_pnl:.4f} | Sharpe: {sharpe:.2f} | Max DD: {max_dd:.4f}")
        log.info(f"Regime distribution: {regimes.value_counts().to_dict()}")

    return results_df


if __name__ == "__main__":
    log.info("Gold HMM+XGBoost Regime pipeline ready.")
    log.info("Usage: df = pd.read_csv('XAUUSD_H1.csv'); results = backtest(df)")
