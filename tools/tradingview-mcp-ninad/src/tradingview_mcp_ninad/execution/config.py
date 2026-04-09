"""Pydantic configuration for the execution layer.

Loaded from ``execution_config.json`` next to the package root, or from
``~/.tradingview-mcp-ninad/execution_config.json``. Falls back to safe
defaults (paper mode, no broker keys) so the server always starts.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..logging_config import state_dir


class AlpacaConfig(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    paper: bool = True


class MT5Config(BaseModel):
    login: int = 0
    password: str = ""
    server: str = ""
    path: str = ""


class BinanceConfig(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True


class IBKRConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1


class SymbolRouting(BaseModel):
    crypto: str = "binance"
    stocks: str = "alpaca"
    forex: str = "mt5"
    futures: str = "ibkr"


class BrokersConfig(BaseModel):
    alpaca: AlpacaConfig = Field(default_factory=AlpacaConfig)
    mt5: MT5Config = Field(default_factory=MT5Config)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)


class ExecutionConfig(BaseModel):
    """Top-level execution configuration.

    ``mode`` controls which broker receives orders:
    - ``paper`` — built-in in-memory simulator (default, zero config)
    - ``paper_broker`` — the broker's own paper/testnet environment
    - ``live`` — real money (gated by ``require_confirmation_for_live``)
    """

    mode: str = "paper"
    paper_balance: float = 100_000.0
    paper_currency: str = "USD"
    max_position_size: float = 10_000.0
    max_open_positions: int = 5
    require_confirmation_for_live: bool = True
    symbol_routing: SymbolRouting = Field(default_factory=SymbolRouting)
    brokers: BrokersConfig = Field(default_factory=BrokersConfig)


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_execution_config() -> ExecutionConfig:
    """Search candidate paths and return the first valid config, or defaults."""
    candidates = [
        _PROJECT_ROOT / "execution_config.json",
        state_dir() / "execution_config.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                return ExecutionConfig.model_validate(raw)
            except Exception:
                pass
    return ExecutionConfig()
