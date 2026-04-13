"""
Intelligence Suite — Broker Abstraction
==========================================
Executes trades on MT5, Binance, or paper mode.
Adapted from execution/gemma_trader/broker_bridge.py.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseBroker(ABC):
    @abstractmethod
    def get_balance(self) -> float:
        pass

    @abstractmethod
    def place_order(self, symbol: str, action: str, qty: float,
                    sl: float, tp: float, magic: int = 240411,
                    comment: str = "intelligence-suite") -> dict:
        pass

    @abstractmethod
    def close_position(self, symbol: str, magic: int = 240411) -> dict:
        pass


class PaperBroker(BaseBroker):
    def __init__(self, initial_balance: float = 100_000):
        self.balance = initial_balance
        self.positions = {}
        self.order_history = []
        logger.info(f"Paper broker initialized | Balance: {self.balance}")

    def get_balance(self) -> float:
        return self.balance

    def place_order(self, symbol: str, action: str, qty: float,
                    sl: float, tp: float, magic: int = 240411,
                    comment: str = "intelligence-suite") -> dict:
        order = {
            "order_id": f"PAPER-{len(self.order_history) + 1:04d}",
            "symbol": symbol, "action": action, "qty": qty,
            "sl": sl, "tp": tp, "status": "filled",
            "timestamp": datetime.now().isoformat(),
        }
        self.positions[symbol] = order
        self.order_history.append(order)
        logger.info(f"[PAPER] {action} {qty} {symbol} | SL={sl} TP={tp}")
        return order

    def close_position(self, symbol: str, magic: int = 240411) -> dict:
        if symbol in self.positions:
            pos = self.positions.pop(symbol)
            logger.info(f"[PAPER] Closed {symbol}")
            return {"status": "closed", "position": pos}
        return {"status": "no_position"}


class MT5Broker(BaseBroker):
    def __init__(self, config: dict):
        self.config = config["broker"]["mt5"]
        self.connected = False
        self._connect()

    def _connect(self):
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return
            if self.config.get("login"):
                authorized = mt5.login(
                    login=self.config["login"],
                    password=self.config["password"],
                    server=self.config["server"],
                )
                if not authorized:
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    return
            self.connected = True
            info = mt5.account_info()
            logger.info(f"MT5 broker connected | Account: {info.login} | Balance: {info.balance}")
        except ImportError:
            logger.error("MetaTrader5 not installed")
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")

    def get_balance(self) -> float:
        if not self.connected:
            return 0.0
        info = self.mt5.account_info()
        return info.balance if info else 0.0

    def _get_filling_mode(self, symbol: str):
        info = self.mt5.symbol_info(symbol)
        if info is None:
            return self.mt5.ORDER_FILLING_IOC
        filling = info.filling_mode
        if filling & 1:
            return self.mt5.ORDER_FILLING_FOK
        elif filling & 2:
            return self.mt5.ORDER_FILLING_IOC
        return self.mt5.ORDER_FILLING_RETURN

    def place_order(self, symbol: str, action: str, qty: float,
                    sl: float, tp: float, magic: int = 240411,
                    comment: str = "intelligence-suite") -> dict:
        if not self.connected:
            return {"status": "error", "reason": "not connected"}

        order_type = self.mt5.ORDER_TYPE_BUY if action == "BUY" else self.mt5.ORDER_TYPE_SELL
        tick = self.mt5.symbol_info_tick(symbol)
        if not tick:
            return {"status": "error", "reason": f"Cannot get price for {symbol}"}

        price = tick.ask if action == "BUY" else tick.bid
        filling_mode = self._get_filling_mode(symbol)

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol, "volume": qty, "type": order_type,
            "price": price, "sl": sl, "tp": tp,
            "magic": magic, "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            # Retry with alternative filling modes
            if result.retcode == 10030:
                for alt in [self.mt5.ORDER_FILLING_FOK, self.mt5.ORDER_FILLING_RETURN]:
                    if alt == filling_mode:
                        continue
                    request["type_filling"] = alt
                    result = self.mt5.order_send(request)
                    if result.retcode == self.mt5.TRADE_RETCODE_DONE:
                        break
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return {"status": "error", "retcode": result.retcode, "comment": result.comment}

        logger.info(f"MT5 {action} {qty} {symbol} @ {price} | SL={sl} TP={tp}")
        return {
            "status": "filled", "order_id": result.order,
            "price": price, "symbol": symbol, "action": action,
            "qty": qty, "sl": sl, "tp": tp,
        }

    def close_position(self, symbol: str, magic: int = 240411) -> dict:
        if not self.connected:
            return {"status": "error", "reason": "not connected"}
        positions = self.mt5.positions_get(symbol=symbol)
        if not positions:
            return {"status": "no_position"}
        for pos in positions:
            if pos.magic != magic:
                continue
            close_type = self.mt5.ORDER_TYPE_SELL if pos.type == 0 else self.mt5.ORDER_TYPE_BUY
            tick = self.mt5.symbol_info_tick(symbol)
            price = tick.bid if pos.type == 0 else tick.ask
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol, "volume": pos.volume,
                "type": close_type, "position": pos.ticket,
                "price": price, "magic": magic, "comment": "suite-close",
            }
            self.mt5.order_send(request)
        return {"status": "closed"}


class BinanceBroker(BaseBroker):
    def __init__(self, config: dict):
        self.config = config["broker"]["binance"]
        self.exchange = None
        self._connect()

    def _connect(self):
        try:
            import ccxt
            self.exchange = ccxt.binance({
                "apiKey": self.config["api_key"],
                "secret": self.config["api_secret"],
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            })
            balance = self.exchange.fetch_balance()
            logger.info(f"Binance connected | USDT: {balance['USDT']['free']}")
        except ImportError:
            logger.error("ccxt not installed. Run: pip install ccxt")
        except Exception as e:
            logger.error(f"Binance connection error: {e}")

    def get_balance(self) -> float:
        if not self.exchange:
            return 0.0
        return float(self.exchange.fetch_balance()["USDT"]["free"])

    def place_order(self, symbol: str, action: str, qty: float,
                    sl: float, tp: float, magic: int = 240411,
                    comment: str = "intelligence-suite") -> dict:
        if not self.exchange:
            return {"status": "error", "reason": "not connected"}
        try:
            side = "buy" if action == "BUY" else "sell"
            order = self.exchange.create_market_order(symbol, side, qty)
            sl_side = "sell" if action == "BUY" else "buy"
            self.exchange.create_order(symbol, "stop_market", sl_side, qty,
                                       params={"stopPrice": sl})
            self.exchange.create_order(symbol, "take_profit_market", sl_side, qty,
                                       params={"stopPrice": tp})
            return {"status": "filled", "order": order}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def close_position(self, symbol: str, magic: int = 240411) -> dict:
        if not self.exchange:
            return {"status": "error"}
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if float(pos["contracts"]) > 0:
                    side = "sell" if pos["side"] == "long" else "buy"
                    self.exchange.create_market_order(
                        symbol, side, pos["contracts"],
                        params={"reduceOnly": True},
                    )
            return {"status": "closed"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}


def create_broker(config: dict) -> BaseBroker:
    """Factory: create the right broker based on config."""
    mode = config.get("trading", {}).get("mode", "paper")
    if mode == "paper":
        return PaperBroker()

    broker_name = config.get("broker", {}).get("name", "paper")
    if broker_name == "mt5":
        return MT5Broker(config)
    elif broker_name == "binance":
        return BinanceBroker(config)
    else:
        logger.warning(f"Unknown broker '{broker_name}', falling back to paper")
        return PaperBroker()
