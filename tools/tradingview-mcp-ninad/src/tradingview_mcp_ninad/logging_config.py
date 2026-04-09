"""Structured logging that never touches stdout.

The MCP stdio transport multiplexes JSON-RPC frames over stdout. A stray
``print`` or a logger with a ``StreamHandler(sys.stdout)`` will corrupt the
protocol and the client will silently disconnect. This module configures
``structlog`` and the stdlib root logger to write **only** to a rotating file
under :func:`state_dir`, and rebinds any existing handlers to that sink so
imported third-party libraries can't leak to stdout either.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

import structlog


def state_dir() -> Path:
    """Return the on-disk directory for logs and saved sessions.

    Honors ``TVMCP_STATE_DIR`` so power users can redirect everything to a
    project-local folder. Falls back to ``~/.tradingview-mcp-ninad``.
    """
    raw = os.environ.get("TVMCP_STATE_DIR", "~/.tradingview-mcp-ninad")
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging() -> structlog.stdlib.BoundLogger:
    """Wire up structlog + stdlib logging to a file-only sink.

    Idempotent: calling more than once replaces existing handlers instead of
    stacking them, which matters because the MCP server reloads modules
    during integration tests.
    """
    log_dir = state_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "server.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    # Drop any inherited handlers — particularly anything attached to stdout.
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(file_handler)
    root.setLevel(logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _assert_no_stdout_handlers()
    return structlog.get_logger("tradingview_mcp_ninad")


def _assert_no_stdout_handlers() -> None:
    """Defense-in-depth check that nothing logs to stdout.

    Raised at import time so a misconfigured dependency never silently
    poisons the MCP transport in production.
    """
    for logger in [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]:
        for handler in getattr(logger, "handlers", []):
            stream = getattr(handler, "stream", None)
            if stream is sys.stdout:
                raise RuntimeError(
                    f"Logger {logger.name!r} has a stdout handler — this would corrupt MCP frames"
                )
