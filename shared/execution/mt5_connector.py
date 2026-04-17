"""
ReySentinel — MT5 Connector
====================================
Fetches live candle data and manages positions via MetaTrader 5.
Adapted from execution/gemma_trader/mt5_data_feed.py.
Supports multi-account connections.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5

    TIMEFRAME_MAP = {
        "1m": mt5.TIMEFRAME_M1, "2m": mt5.TIMEFRAME_M2,
        "3m": mt5.TIMEFRAME_M3, "5m": mt5.TIMEFRAME_M5,
        "10m": mt5.TIMEFRAME_M10, "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30, "1h": mt5.TIMEFRAME_H1,
        "2h": mt5.TIMEFRAME_H2, "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1, "1w": mt5.TIMEFRAME_W1,
        "1M": mt5.TIMEFRAME_MN1,
    }
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    TIMEFRAME_MAP = {}
    mt5 = None
    logger.warning("MetaTrader5 package not installed. Run: pip install MetaTrader5")


class MT5Connector:
    """
    Fetches candle data, tick prices, positions, and deal history
    from MetaTrader 5.
    """

    def __init__(self, config: dict):
        if not MT5_AVAILABLE:
            raise ImportError("MetaTrader5 package not installed.")
        self.config = config
        self.mt5_config = config.get("broker", {}).get("mt5", {})
        self.connected = False
        self._connect()

    def _connect(self):
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return

            login = self.mt5_config.get("login", 0)
            if login and login != 0:
                authorized = mt5.login(
                    login=int(login),
                    password=str(self.mt5_config.get("password", "")),
                    server=str(self.mt5_config.get("server", "")),
                )
                if not authorized:
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    return

            self.connected = True
            account = mt5.account_info()
            if account:
                logger.info(
                    f"MT5 connected | Account: {account.login} | "
                    f"Server: {account.server} | Balance: {account.balance}"
                )
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")

    def ensure_symbol(self, symbol: str) -> bool:
        if not self.connected:
            return False
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol '{symbol}' not found in MT5")
            return False
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to select '{symbol}' in Market Watch")
                return False
        return True

    def get_candles(self, symbol: str, timeframe_str: str,
                    n_bars: int = 500) -> pd.DataFrame:
        if not self.connected:
            return pd.DataFrame()
        if not self.ensure_symbol(symbol):
            return pd.DataFrame()

        tf = TIMEFRAME_MAP.get(timeframe_str)
        if tf is None:
            logger.error(f"Unknown timeframe: {timeframe_str}")
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to get candles for {symbol}: {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        if "tick_volume" in df.columns:
            df["volume"] = df["tick_volume"]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        return df

    def get_tick(self, symbol: str) -> dict:
        if not self.connected or not self.ensure_symbol(symbol):
            return {}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {
            "bid": tick.bid, "ask": tick.ask, "last": tick.last,
            "volume": tick.volume,
            "time": datetime.fromtimestamp(tick.time).isoformat(),
        }

    def get_positions(self, symbol: str = None, magic: int = None) -> list:
        if not self.connected:
            return []
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []

        result = []
        for pos in positions:
            if magic is not None and pos.magic != magic:
                continue
            result.append({
                "ticket": pos.ticket, "symbol": pos.symbol,
                "type": "BUY" if pos.type == 0 else "SELL",
                "volume": pos.volume, "price_open": pos.price_open,
                "sl": pos.sl, "tp": pos.tp,
                "price_current": pos.price_current, "profit": pos.profit,
                "swap": pos.swap, "magic": pos.magic, "comment": pos.comment,
                "time": datetime.fromtimestamp(pos.time).isoformat(),
            })
        return result

    def get_account_info(self) -> dict:
        if not self.connected:
            return {}
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "login": info.login, "server": info.server,
            "balance": info.balance, "equity": info.equity,
            "margin": info.margin, "free_margin": info.margin_free,
            "profit": info.profit, "leverage": info.leverage,
            "currency": info.currency,
        }

    def get_deals_history(self, days: int = 7, magic: int = None) -> list:
        if not self.connected:
            return []
        date_from = datetime.now() - timedelta(days=days)
        deals = mt5.history_deals_get(date_from, datetime.now())
        if deals is None:
            return []

        result = []
        for deal in deals:
            if magic is not None and deal.magic != magic:
                continue
            result.append({
                "ticket": deal.ticket, "order": deal.order,
                "symbol": deal.symbol,
                "type": "BUY" if deal.type == 0 else "SELL",
                "volume": deal.volume, "price": deal.price,
                "profit": deal.profit, "swap": deal.swap,
                "commission": deal.commission, "comment": deal.comment,
                "magic": deal.magic,
                "time": datetime.fromtimestamp(deal.time).isoformat(),
            })
        return result

    def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol specifications for lot sizing."""
        if not self.connected:
            return {}
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return {
            "tick_size": info.trade_tick_size,
            "tick_value": info.trade_tick_value,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "contract_size": info.trade_contract_size,
            "digits": info.digits,
        }

    def shutdown(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 disconnected")
