"""
Unified logging configuration for the Intelligence Suite.
"""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure logging for all modules."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    log_format = (
        "%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root.addHandler(console)

    # File handler
    fh = logging.FileHandler(
        Path(log_dir) / "intelligence_suite.log", encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root.addHandler(fh)
