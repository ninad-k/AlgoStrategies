"""Centralized logging configuration for TeleTrader."""

from __future__ import annotations

import logging
import sys

from teletrader.config import settings


def setup_logging() -> None:
    """Configure logging for all TeleTrader components.

    - Console: human-readable format
    - File: detailed format with timestamps for audit trail
    """
    root_logger = logging.getLogger("teletrader")
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root_logger.addHandler(console)

    # File handler
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        file_fmt = "%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s"
        file_handler.setFormatter(logging.Formatter(file_fmt, datefmt=datefmt))
        root_logger.addHandler(file_handler)
