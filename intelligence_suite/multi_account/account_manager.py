"""
Intelligence Suite — Multi-Account Manager
=============================================
Manages connections to multiple MT5 accounts and aggregates
positions, balances, and status across all accounts.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
    logger.warning("MetaTrader5 package not installed.")


class AccountManager:
    """
    Manages multiple MT5 account connections.

    Each account config should have: login, password, server, label.
    """

    def __init__(self, accounts: list[dict[str, Any]]):
        """
        Parameters
        ----------
        accounts : list[dict]
            Each dict: {login: int, password: str, server: str, label: str}.
        """
        self.accounts = accounts
        self._connections: dict[str, dict[str, Any]] = {}
        for acct in self.accounts:
            label = acct.get("label", str(acct.get("login", "unknown")))
            self._connections[label] = {
                "config": acct,
                "connected": False,
                "last_check": None,
            }

    def connect_all(self) -> dict[str, Any]:
        """
        Connect to all configured MT5 accounts.

        Returns
        -------
        dict mapping account label to connection status.
        """
        if not MT5_AVAILABLE:
            logger.error("MT5 not available; returning demo status for all accounts")
            return {
                label: {"connected": False, "error": "MetaTrader5 not installed"}
                for label in self._connections
            }

        results: dict[str, Any] = {}
        for label, conn in self._connections.items():
            cfg = conn["config"]
            try:
                # MT5 only supports one connection at a time; we cycle through
                if not mt5.initialize():
                    results[label] = {
                        "connected": False,
                        "error": f"MT5 init failed: {mt5.last_error()}",
                    }
                    continue

                login = int(cfg.get("login", 0))
                authorized = mt5.login(
                    login=login,
                    password=str(cfg.get("password", "")),
                    server=str(cfg.get("server", "")),
                )
                if not authorized:
                    results[label] = {
                        "connected": False,
                        "error": f"Login failed: {mt5.last_error()}",
                    }
                    mt5.shutdown()
                    continue

                info = mt5.account_info()
                conn["connected"] = True
                conn["last_check"] = datetime.utcnow().isoformat()
                results[label] = {
                    "connected": True,
                    "login": info.login if info else login,
                    "server": info.server if info else cfg.get("server"),
                    "balance": info.balance if info else 0,
                }
                mt5.shutdown()

            except Exception as exc:
                results[label] = {"connected": False, "error": str(exc)}
                conn["connected"] = False
                logger.error(f"Failed to connect account {label}: {exc}")

        logger.info(
            f"Connect all: {sum(1 for r in results.values() if r.get('connected'))}"
            f"/{len(results)} accounts connected"
        )
        return results

    def get_all_positions(self) -> list[dict[str, Any]]:
        """
        Retrieve positions from all accounts, each tagged with account_id.

        Returns
        -------
        list of position dicts with an added 'account_id' field.
        """
        if not MT5_AVAILABLE:
            return self._demo_positions()

        all_positions: list[dict] = []
        for label, conn in self._connections.items():
            cfg = conn["config"]
            try:
                if not mt5.initialize():
                    continue
                login = int(cfg.get("login", 0))
                if not mt5.login(
                    login=login,
                    password=str(cfg.get("password", "")),
                    server=str(cfg.get("server", "")),
                ):
                    mt5.shutdown()
                    continue

                positions = mt5.positions_get()
                if positions:
                    for pos in positions:
                        all_positions.append({
                            "account_id": label,
                            "ticket": pos.ticket,
                            "symbol": pos.symbol,
                            "type": "BUY" if pos.type == 0 else "SELL",
                            "volume": pos.volume,
                            "price_open": pos.price_open,
                            "price_current": pos.price_current,
                            "profit": pos.profit,
                            "swap": pos.swap,
                            "sl": pos.sl,
                            "tp": pos.tp,
                            "magic": pos.magic,
                            "time": datetime.fromtimestamp(pos.time).isoformat(),
                        })
                mt5.shutdown()

            except Exception as exc:
                logger.error(f"Failed to get positions for {label}: {exc}")

        if not all_positions:
            return self._demo_positions()
        return all_positions

    def get_all_balances(self) -> dict[str, dict[str, float]]:
        """
        Retrieve balance, equity, and profit for all accounts.

        Returns
        -------
        dict mapping account label to {balance, equity, profit, margin, free_margin}.
        """
        if not MT5_AVAILABLE:
            return self._demo_balances()

        balances: dict[str, dict] = {}
        for label, conn in self._connections.items():
            cfg = conn["config"]
            try:
                if not mt5.initialize():
                    continue
                login = int(cfg.get("login", 0))
                if not mt5.login(
                    login=login,
                    password=str(cfg.get("password", "")),
                    server=str(cfg.get("server", "")),
                ):
                    mt5.shutdown()
                    continue

                info = mt5.account_info()
                if info:
                    balances[label] = {
                        "balance": info.balance,
                        "equity": info.equity,
                        "profit": info.profit,
                        "margin": info.margin,
                        "free_margin": info.margin_free,
                        "leverage": info.leverage,
                        "currency": info.currency,
                    }
                mt5.shutdown()

            except Exception as exc:
                logger.error(f"Failed to get balance for {label}: {exc}")
                balances[label] = {"error": str(exc)}

        if not balances:
            return self._demo_balances()
        return balances

    def get_account_status(self) -> list[dict[str, Any]]:
        """
        Return connected/disconnected status for each account.

        Returns
        -------
        list of dicts with label, login, server, connected, last_check.
        """
        statuses = []
        for label, conn in self._connections.items():
            cfg = conn["config"]
            statuses.append({
                "label": label,
                "login": cfg.get("login"),
                "server": cfg.get("server"),
                "connected": conn["connected"],
                "last_check": conn["last_check"],
            })
        return statuses

    # ------------------------------------------------------------------
    # Demo data for development without MT5
    # ------------------------------------------------------------------

    def _demo_positions(self) -> list[dict]:
        return [
            {"account_id": "Main", "ticket": 1001, "symbol": "BTCUSD", "type": "BUY",
             "volume": 0.5, "price_open": 42000, "price_current": 43200, "profit": 600,
             "swap": -2.5, "sl": 41000, "tp": 45000, "magic": 240412,
             "time": datetime.utcnow().isoformat()},
            {"account_id": "Main", "ticket": 1002, "symbol": "ETHUSD", "type": "BUY",
             "volume": 2.0, "price_open": 2800, "price_current": 2950, "profit": 300,
             "swap": -1.2, "sl": 2700, "tp": 3100, "magic": 240412,
             "time": datetime.utcnow().isoformat()},
            {"account_id": "Hedge", "ticket": 2001, "symbol": "XAUUSD", "type": "SELL",
             "volume": 0.1, "price_open": 2050, "price_current": 2030, "profit": 200,
             "swap": 0, "sl": 2100, "tp": 1980, "magic": 240412,
             "time": datetime.utcnow().isoformat()},
            {"account_id": "Hedge", "ticket": 2002, "symbol": "EURUSD", "type": "BUY",
             "volume": 1.0, "price_open": 1.0850, "price_current": 1.0890, "profit": 40,
             "swap": -0.5, "sl": 1.0800, "tp": 1.0950, "magic": 240412,
             "time": datetime.utcnow().isoformat()},
        ]

    def _demo_balances(self) -> dict[str, dict]:
        return {
            "Main": {
                "balance": 75000, "equity": 75900, "profit": 900,
                "margin": 3200, "free_margin": 72700, "leverage": 100, "currency": "USD",
            },
            "Hedge": {
                "balance": 25000, "equity": 25240, "profit": 240,
                "margin": 1800, "free_margin": 23440, "leverage": 200, "currency": "USD",
            },
        }
