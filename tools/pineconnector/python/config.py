"""PineConnector configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# --- Server ---
HOST = _env("HOST", "0.0.0.0")
PORT = _env_int("PORT", 8003)

# --- Authentication ---
WEBHOOK_TOKEN = _env("WEBHOOK_TOKEN")

# --- ZMQ addresses ---
ZMQ_SIGNAL_ADDR = _env("ZMQ_SIGNAL_ADDR", "tcp://127.0.0.1:5555")
ZMQ_COMMAND_ADDR = _env("ZMQ_COMMAND_ADDR", "tcp://127.0.0.1:5556")
ZMQ_RESULT_ADDR = _env("ZMQ_RESULT_ADDR", "tcp://127.0.0.1:5557")
ZMQ_STATE_ADDR = _env("ZMQ_STATE_ADDR", "tcp://127.0.0.1:5558")

# --- MT5 bridge ---
MT5_BRIDGE_MODE = _env("MT5_BRIDGE_MODE", "python")  # "python" or "mql5"
MT5_PATH = _env("MT5_PATH")
MT5_LOGIN = _env_int("MT5_LOGIN")
MT5_PASSWORD = _env("MT5_PASSWORD")
MT5_SERVER = _env("MT5_SERVER")

# --- Database ---
DB_BACKEND = _env("DB_BACKEND", "sqlite")  # "sqlite" or "postgresql"
DB_PATH = Path(__file__).parent.parent / "data" / "pineconnector.db"
PG_DSN = _env("PG_DSN")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID")

# --- Modes ---
DRY_RUN = _env_bool("DRY_RUN", False)
