"""
Data Prep — Generates grayscale candlestick chart images for CNN training.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def ohlcv_to_image(df: pd.DataFrame, size: int = 64) -> np.ndarray:
    """
    Convert an OHLCV window into a grayscale image for CNN input.

    Creates a simplified candlestick chart as a 2D numpy array.
    Green (up) candles = bright, Red (down) candles = dark.

    Args:
        df: OHLCV DataFrame (window_size rows)
        size: Output image size (size x size)

    Returns:
        numpy array of shape (size, size), values 0-255
    """
    if df is None or len(df) < 2:
        return np.zeros((size, size), dtype=np.uint8)

    n_bars = len(df)
    image = np.zeros((size, size), dtype=np.uint8)

    # Normalize prices to fit image
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    price_range = price_max - price_min
    if price_range == 0:
        return image

    def price_to_y(price):
        # Invert Y (high price = top of image = low Y)
        normalized = (float(price) - price_min) / price_range
        return int((1 - normalized) * (size - 1))

    bar_width = max(1, size // n_bars)

    for i, (_, row) in enumerate(df.iterrows()):
        x_center = int((i + 0.5) * size / n_bars)
        x_start = max(0, x_center - bar_width // 2)
        x_end = min(size - 1, x_center + bar_width // 2)

        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

        y_high = price_to_y(h)
        y_low = price_to_y(l)
        y_open = price_to_y(o)
        y_close = price_to_y(c)

        is_up = c >= o
        body_brightness = 200 if is_up else 80
        wick_brightness = 140

        # Draw wick (high-low line)
        y_wick_top = min(y_high, y_low)
        y_wick_bot = max(y_high, y_low)
        wick_x = (x_start + x_end) // 2
        if 0 <= wick_x < size:
            for y in range(max(0, y_wick_top), min(size, y_wick_bot + 1)):
                image[y, wick_x] = wick_brightness

        # Draw body (open-close rectangle)
        y_body_top = min(y_open, y_close)
        y_body_bot = max(y_open, y_close)
        if y_body_top == y_body_bot:
            y_body_bot = y_body_top + 1  # Ensure at least 1 pixel

        for x in range(max(0, x_start), min(size, x_end + 1)):
            for y in range(max(0, y_body_top), min(size, y_body_bot + 1)):
                image[y, x] = body_brightness

    return image


def generate_training_windows(df: pd.DataFrame, window_size: int = 64,
                               stride: int = 16) -> list[pd.DataFrame]:
    """
    Generate sliding windows of OHLCV data for training.

    Args:
        df: Full OHLCV DataFrame
        window_size: Number of bars per window
        stride: Step between windows

    Returns:
        List of DataFrames, each window_size rows
    """
    windows = []
    for i in range(0, len(df) - window_size + 1, stride):
        windows.append(df.iloc[i:i + window_size].copy())
    return windows
