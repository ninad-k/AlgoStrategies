"""Unit tests for ML SuperTrend feature pipeline (no MetaTrader connection)."""

import numpy as np
import pandas as pd
import pytest

from core.data_fetcher import add_base_indicators
from core.feature_engine import (
    build_features_for_inference,
    build_full_feature_matrix,
    build_supertrend_features,
    compute_supertrend_single,
    create_labels,
)


def test_add_base_indicators_shapes(sample_ohlcv: pd.DataFrame):
    df = add_base_indicators(sample_ohlcv)
    assert "atr" in df.columns and "hl2" in df.columns
    assert "rsi" in df.columns and "norm_volatility" in df.columns
    assert len(df) == len(sample_ohlcv)


def test_compute_supertrend_single(sample_ohlcv: pd.DataFrame):
    df = add_base_indicators(sample_ohlcv)
    st = compute_supertrend_single(df, factor=3.0)
    assert "st_3.0_trend" in st.columns
    assert len(st) == len(df)
    assert st["st_3.0_trend"].dtype in (np.int32, np.int64)


def test_build_supertrend_features(sample_ohlcv: pd.DataFrame):
    df = add_base_indicators(sample_ohlcv)
    feat = build_supertrend_features(df, min_factor=1.0, max_factor=2.0, step=0.5)
    assert "st_bullish_pct" in feat.columns
    assert "st_avg_perf" in feat.columns
    assert len(feat) == len(df)


def test_create_labels(sample_ohlcv: pd.DataFrame):
    df = add_base_indicators(sample_ohlcv)
    labels = create_labels(df, forward_bars=10, min_move_atr=0.5)
    assert labels.name == "label"
    assert set(np.unique(labels.dropna().values)).issubset({-1, 0, 1})


def test_build_full_feature_matrix(sample_ohlcv: pd.DataFrame):
    X, y = build_full_feature_matrix(sample_ohlcv, higher_tf_data=None, forward_bars=10, min_move_atr=1.0)
    assert len(X) == len(y)
    assert len(X) > 0
    assert not X.columns.duplicated().any()
    assert y.dtype in (np.int32, np.int64)


def test_build_features_for_inference_latest_row(sample_ohlcv: pd.DataFrame):
    row = build_features_for_inference(sample_ohlcv, higher_tf_data=None, min_bars=120)
    assert len(row) == 1
    assert row.shape[1] > 10


def test_build_full_feature_matrix_with_htf(sample_ohlcv: pd.DataFrame):
    htf = sample_ohlcv.iloc[::3].copy()
    htf.index = pd.date_range("2024-01-01", periods=len(htf), freq="h", tz="UTC")
    htf.index.name = "time"
    X, y = build_full_feature_matrix(
        sample_ohlcv,
        higher_tf_data={"H1": htf},
        forward_bars=10,
        min_move_atr=1.0,
    )
    assert len(X) == len(y)
    htf_cols = [c for c in X.columns if c.startswith("htf_H1")]
    assert len(htf_cols) > 0
