# Feature Engineering for ML SuperTrend
# Author: Ninad
#
# Builds the feature matrix from multi-factor SuperTrend calculations and
# multi-timeframe context. Each row is a bar with features + a forward-looking
# label (profitable trade direction over the next N bars).

import pandas as pd
import numpy as np
import talib
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def compute_supertrend_single(df: pd.DataFrame, factor: float, atr_col: str = 'atr') -> pd.DataFrame:
    """Vectorized SuperTrend for a single ATR factor. Returns trend, output, perf columns."""
    n = len(df)
    hl2 = df['hl2'].values
    atr = df[atr_col].values
    close = df['close'].values
    norm_vol = df['norm_volatility'].values

    upper = hl2 + atr * factor
    lower = hl2 - atr * factor
    trend = np.zeros(n, dtype=np.int32)
    output = np.zeros(n, dtype=np.float64)
    perf = np.zeros(n, dtype=np.float64)
    vol_adj_perf = np.zeros(n, dtype=np.float64)

    alpha = 2 / (10 + 1)  # perf_alpha = 10

    for i in range(1, n):
        if close[i] > upper[i - 1]:
            trend[i] = 1
        elif close[i] < lower[i - 1]:
            trend[i] = 0
        else:
            trend[i] = trend[i - 1]

        if trend[i] == 1:
            if trend[i - 1] == 1:
                lower[i] = max(lower[i], lower[i - 1])
            output[i] = lower[i]
        else:
            if trend[i - 1] == 0:
                upper[i] = min(upper[i], upper[i - 1])
            output[i] = upper[i]

        price_change = close[i] - close[i - 1]
        direction = np.sign(close[i - 1] - output[i - 1])
        raw_perf = price_change * direction

        perf[i] = alpha * raw_perf + (1 - alpha) * perf[i - 1]
        denom = 1 + norm_vol[i] if not np.isnan(norm_vol[i]) else 1
        vol_adj = raw_perf / denom
        vol_adj_perf[i] = alpha * vol_adj + (1 - alpha) * vol_adj_perf[i - 1]

    return pd.DataFrame({
        f'st_{factor}_trend': trend,
        f'st_{factor}_output': output,
        f'st_{factor}_perf': perf,
        f'st_{factor}_vol_adj_perf': vol_adj_perf,
        f'st_{factor}_dist': (close - output) / atr,  # distance from ST line in ATR units
    }, index=df.index)


def build_supertrend_features(
    df: pd.DataFrame,
    min_factor: float = 1.0,
    max_factor: float = 5.0,
    step: float = 0.5,
) -> pd.DataFrame:
    """Compute SuperTrend across all factors and aggregate into feature columns."""
    factors = np.arange(min_factor, max_factor + step, step)
    all_st = []

    for factor in factors:
        st = compute_supertrend_single(df, round(factor, 1))
        all_st.append(st)

    features = pd.concat(all_st, axis=1)

    # Aggregate features across all factors
    trend_cols = [c for c in features.columns if c.endswith('_trend')]
    perf_cols = [c for c in features.columns if c.endswith('_vol_adj_perf')]
    dist_cols = [c for c in features.columns if c.endswith('_dist')]

    features['st_bullish_pct'] = features[trend_cols].mean(axis=1)  # % of factors that are bullish
    features['st_avg_perf'] = features[perf_cols].mean(axis=1)
    features['st_perf_std'] = features[perf_cols].std(axis=1)      # disagreement among factors
    features['st_best_perf'] = features[perf_cols].max(axis=1)
    features['st_worst_perf'] = features[perf_cols].min(axis=1)
    features['st_perf_spread'] = features['st_best_perf'] - features['st_worst_perf']
    features['st_avg_dist'] = features[dist_cols].mean(axis=1)

    # Consensus: trend flips where majority of factors agree
    features['st_consensus_shift'] = features['st_bullish_pct'].diff()

    return features


def build_mtf_features(
    target_df: pd.DataFrame,
    higher_tf_data: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Merge higher-timeframe context features into the target timeframe via asof join.

    For each higher TF, we forward-fill its trend/momentum onto the target TF bars
    so the model knows the broader market context at each decision point.
    """
    result = target_df.copy()

    for tf_name, htf_df in higher_tf_data.items():
        if htf_df is None or len(htf_df) < 50:
            continue

        prefix = f"htf_{tf_name}"
        htf = htf_df.copy()

        # Compute basic higher-TF features
        htf[f'{prefix}_rsi'] = talib.RSI(htf['close'], timeperiod=14)
        htf[f'{prefix}_adx'] = talib.ADX(htf['high'], htf['low'], htf['close'], timeperiod=14)
        htf[f'{prefix}_atr_norm'] = (
            talib.ATR(htf['high'], htf['low'], htf['close'], timeperiod=14) / htf['close']
        )
        ema_f = talib.EMA(htf['close'], timeperiod=12)
        ema_s = talib.EMA(htf['close'], timeperiod=26)
        htf[f'{prefix}_ema_trend'] = (ema_f - ema_s) / htf['close']
        htf[f'{prefix}_ret5'] = htf['close'].pct_change(5)

        # SuperTrend trend on higher TF (factor=3 as a representative)
        if 'hl2' not in htf.columns:
            htf['hl2'] = (htf['high'] + htf['low']) / 2
        atr_htf = talib.ATR(htf['high'], htf['low'], htf['close'], timeperiod=10)
        if atr_htf is not None:
            htf['atr'] = atr_htf
            htf['norm_volatility'] = htf['close'].rolling(10).std() / htf['close'].rolling(50).std()
            htf['norm_volatility'] = htf['norm_volatility'].fillna(1.0)
            st = compute_supertrend_single(htf, factor=3.0)
            htf[f'{prefix}_st_trend'] = st['st_3.0_trend']

        cols = [c for c in htf.columns if c.startswith(prefix)]
        htf_features = htf[cols]

        # Forward-fill higher TF values onto target TF via merge_asof
        htf_features = htf_features.copy()
        htf_features.index.name = 'time'
        htf_features = htf_features.reset_index()

        result_reset = result.reset_index()
        merged = pd.merge_asof(
            result_reset.sort_values('time'),
            htf_features.sort_values('time'),
            on='time',
            direction='backward',
        )
        merged.set_index('time', inplace=True)

        for col in cols:
            result[col] = merged[col].values

    return result


def create_labels(df: pd.DataFrame, forward_bars: int = 10, min_move_atr: float = 1.0) -> pd.Series:
    """Create trade labels based on future price movement relative to ATR.

    Labels:
        1 = profitable long (price rises > min_move_atr * ATR within forward_bars)
       -1 = profitable short (price drops > min_move_atr * ATR within forward_bars)
        0 = no clear trade (sideways / insufficient move)
    """
    close = df['close'].values
    atr = df['atr'].values
    n = len(df)
    labels = np.zeros(n, dtype=np.int32)

    for i in range(n - forward_bars):
        future_slice = close[i + 1: i + 1 + forward_bars]
        threshold = atr[i] * min_move_atr

        if np.isnan(threshold) or threshold <= 0:
            continue

        max_up = future_slice.max() - close[i]
        max_down = close[i] - future_slice.min()

        # Whichever direction has the larger move wins, but must exceed threshold
        if max_up > threshold and max_up >= max_down:
            labels[i] = 1
        elif max_down > threshold and max_down > max_up:
            labels[i] = -1

    return pd.Series(labels, index=df.index, name='label')


def build_full_feature_matrix(
    target_df: pd.DataFrame,
    higher_tf_data: Dict[str, pd.DataFrame] = None,
    forward_bars: int = 10,
    min_move_atr: float = 1.0,
) -> Tuple[pd.DataFrame, pd.Series]:
    """End-to-end pipeline: raw OHLCV -> feature matrix + labels.

    Returns (X, y) where X has all features and y is the trade direction label.
    """
    from .data_fetcher import add_base_indicators

    # Base indicators on target timeframe
    df = add_base_indicators(target_df)

    # SuperTrend features across multiple ATR factors
    st_features = build_supertrend_features(df)

    # Merge base + supertrend
    features = pd.concat([df, st_features], axis=1)

    # Multi-timeframe context (if provided)
    if higher_tf_data:
        features = build_mtf_features(features, higher_tf_data)

    # Labels
    labels = create_labels(df, forward_bars=forward_bars, min_move_atr=min_move_atr)

    # Drop rows with NaN features or where label can't be computed
    features = features.iloc[50:-forward_bars]
    labels = labels.iloc[50:-forward_bars]

    # Keep only numeric columns that are actual features (drop raw OHLCV)
    drop_cols = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume',
                 'hl2', 'atr', 'volume_ma', 'volatility']
    feature_cols = [c for c in features.columns if c not in drop_cols and features[c].dtype in [np.float64, np.float32, np.int32, np.int64]]

    X = features[feature_cols].copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)

    return X, labels
