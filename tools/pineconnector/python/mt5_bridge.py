"""MT5 Bridge — executes orders via the MetaTrader5 Python package.

Runs in a dedicated daemon thread since the MT5 API is synchronous.
Receives ExecutionCommands via ZMQ PULL, sends ExecutionResults via ZMQ PUSH.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import zmq

from . import config

log = logging.getLogger(__name__)

# MT5 order type mapping
_ORDER_TYPE_MAP = {
    "market_buy": 0,   # ORDER_TYPE_BUY
    "market_sell": 1,   # ORDER_TYPE_SELL
    "buy_limit": 2,     # ORDER_TYPE_BUY_LIMIT
    "sell_limit": 3,     # ORDER_TYPE_SELL_LIMIT
    "buy_stop": 4,       # ORDER_TYPE_BUY_STOP
    "sell_stop": 5,       # ORDER_TYPE_SELL_STOP
}


class MT5Bridge(threading.Thread):
    """Daemon thread that bridges ZMQ commands to MetaTrader 5."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="mt5-bridge")
        self.connected = False
        self._mt5 = None
        self._reconnect_interval = 5.0
        self._max_reconnect_attempts = 10
        self._poll_interval_ms = 1  # 1ms ZMQ poll

    def run(self) -> None:
        # Import MT5 inside thread (Windows COM requirement)
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            log.error(
                "MetaTrader5 package not installed. "
                "Install with: pip install MetaTrader5"
            )
            return

        # Connect to MT5
        if not self._connect_mt5():
            log.error("Failed to connect to MT5 after all retries")
            return

        # Setup ZMQ sockets
        ctx = zmq.Context()
        cmd_socket = ctx.socket(zmq.PULL)
        cmd_socket.setsockopt(zmq.RCVHWM, 1000)
        cmd_socket.bind(config.ZMQ_COMMAND_ADDR)
        log.info("MT5 bridge PULL bound to %s", config.ZMQ_COMMAND_ADDR)

        result_socket = ctx.socket(zmq.PUSH)
        result_socket.setsockopt(zmq.SNDHWM, 1000)
        result_socket.setsockopt(zmq.LINGER, 1000)
        result_socket.connect(config.ZMQ_RESULT_ADDR)
        log.info("MT5 bridge PUSH connected to %s", config.ZMQ_RESULT_ADDR)

        # Also send results to Rust on :5559
        rust_result_addr = "tcp://127.0.0.1:5559"
        rust_result_socket = ctx.socket(zmq.PUSH)
        rust_result_socket.setsockopt(zmq.SNDHWM, 1000)
        rust_result_socket.setsockopt(zmq.LINGER, 1000)
        rust_result_socket.connect(rust_result_addr)
        log.info("MT5 bridge PUSH (Rust) connected to %s", rust_result_addr)

        poller = zmq.Poller()
        poller.register(cmd_socket, zmq.POLLIN)

        log.info("MT5 bridge ready — processing commands")

        while True:
            try:
                socks = dict(poller.poll(timeout=self._poll_interval_ms))
                if cmd_socket in socks:
                    raw = cmd_socket.recv_json()
                    result = self._execute_command(raw)
                    result_json = json.dumps(result)
                    result_socket.send_string(result_json)
                    rust_result_socket.send_string(result_json)
            except zmq.ZMQError as e:
                log.error("ZMQ error in bridge: %s", e)
                time.sleep(0.1)
            except Exception:
                log.exception("Unexpected error in MT5 bridge")
                time.sleep(0.1)

    def _connect_mt5(self) -> bool:
        mt5 = self._mt5
        for attempt in range(1, self._max_reconnect_attempts + 1):
            kwargs = {}
            if config.MT5_PATH:
                kwargs["path"] = config.MT5_PATH
            if config.MT5_LOGIN:
                kwargs["login"] = config.MT5_LOGIN
            if config.MT5_PASSWORD:
                kwargs["password"] = config.MT5_PASSWORD
            if config.MT5_SERVER:
                kwargs["server"] = config.MT5_SERVER

            if mt5.initialize(**kwargs):
                info = mt5.account_info()
                if info:
                    log.info(
                        "MT5 connected: account=%d server=%s balance=%.2f",
                        info.login, info.server, info.balance,
                    )
                    self.connected = True
                    return True

            error = mt5.last_error()
            log.warning("MT5 connect attempt %d/%d failed: %s", attempt, self._max_reconnect_attempts, error)
            time.sleep(self._reconnect_interval)

        return False

    def _execute_command(self, cmd: dict) -> dict:
        action = cmd.get("action", "")
        now = datetime.now(timezone.utc).isoformat()

        try:
            if action == "place_order":
                return self._place_order(cmd, now)
            elif action == "close_order":
                return self._close_order(cmd, now)
            elif action == "modify_order":
                return self._modify_order(cmd, now)
            else:
                return self._error_result(cmd, now, -1, f"Unknown action: {action}")
        except Exception as e:
            log.exception("Error executing %s", action)
            return self._error_result(cmd, now, -1, str(e))

    def _place_order(self, cmd: dict, now: str) -> dict:
        mt5 = self._mt5
        order_type = _ORDER_TYPE_MAP.get(cmd.get("order_type", ""), -1)
        if order_type == -1:
            return self._error_result(cmd, now, -1, f"Unknown order_type: {cmd.get('order_type')}")

        symbol = cmd["symbol"]
        lot = cmd["lot"]

        # Get current price for market orders
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return self._error_result(cmd, now, -1, f"No tick data for {symbol}")

        if order_type == 0:  # BUY
            price = tick.ask
        elif order_type == 1:  # SELL
            price = tick.bid
        else:
            price = cmd.get("price", 0)

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type <= 1 else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": cmd.get("magic", 0),
            "comment": cmd.get("comment", "PineConnector"),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if cmd.get("sl", 0) > 0:
            request["sl"] = cmd["sl"]
        if cmd.get("tp", 0) > 0:
            request["tp"] = cmd["tp"]

        result = mt5.order_send(request)
        if result is None:
            return self._error_result(cmd, now, -1, "order_send returned None")

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("Order placed: ticket=%d %s %s %.2f @ %.5f", result.order, cmd.get("order_type"), symbol, lot, result.price)
            return {
                "command_id": cmd.get("command_id", ""),
                "signal_id": cmd.get("signal_id", ""),
                "success": True,
                "ticket": result.order,
                "executed_price": result.price,
                "executed_lot": result.volume,
                "error_code": 0,
                "error_message": "",
                "timestamp": now,
            }
        else:
            return self._error_result(cmd, now, result.retcode, result.comment)

    def _close_order(self, cmd: dict, now: str) -> dict:
        mt5 = self._mt5
        ticket = cmd.get("ticket", 0)
        lot = cmd.get("lot", 0)

        if ticket <= 0:
            return self._error_result(cmd, now, -1, "Invalid ticket for close")

        # Get position info
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return self._error_result(cmd, now, -1, f"Position {ticket} not found")

        pos = position[0]
        close_lot = lot if lot > 0 else pos.volume

        # Determine close direction
        if pos.type == 0:  # BUY position — close with SELL
            close_type = 1
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if tick else 0
        else:  # SELL position — close with BUY
            close_type = 0
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.ask if tick else 0

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_lot,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": cmd.get("magic", 0),
            "comment": cmd.get("comment", "PC_close"),
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            return self._error_result(cmd, now, -1, "close order_send returned None")

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("Position closed: ticket=%d lot=%.2f @ %.5f", ticket, close_lot, result.price)
            return {
                "command_id": cmd.get("command_id", ""),
                "signal_id": cmd.get("signal_id", ""),
                "success": True,
                "ticket": ticket,
                "executed_price": result.price,
                "executed_lot": result.volume,
                "error_code": 0,
                "error_message": "",
                "timestamp": now,
            }
        else:
            return self._error_result(cmd, now, result.retcode, result.comment)

    def _modify_order(self, cmd: dict, now: str) -> dict:
        mt5 = self._mt5
        ticket = cmd.get("ticket", 0)

        if ticket <= 0:
            return self._error_result(cmd, now, -1, "Invalid ticket for modify")

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return self._error_result(cmd, now, -1, f"Position {ticket} not found for modify")

        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": cmd.get("sl", pos.sl),
            "tp": cmd.get("tp", pos.tp),
        }

        result = mt5.order_send(request)
        if result is None:
            return self._error_result(cmd, now, -1, "modify order_send returned None")

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("Position modified: ticket=%d sl=%.5f tp=%.5f", ticket, cmd.get("sl", 0), cmd.get("tp", 0))
            return {
                "command_id": cmd.get("command_id", ""),
                "signal_id": cmd.get("signal_id", ""),
                "success": True,
                "ticket": ticket,
                "executed_price": 0,
                "executed_lot": 0,
                "error_code": 0,
                "error_message": "",
                "timestamp": now,
            }
        else:
            return self._error_result(cmd, now, result.retcode, result.comment)

    @staticmethod
    def _error_result(cmd: dict, now: str, code: int, message: str) -> dict:
        log.warning("MT5 error: code=%d msg=%s cmd=%s", code, message, cmd.get("command_id", ""))
        return {
            "command_id": cmd.get("command_id", ""),
            "signal_id": cmd.get("signal_id", ""),
            "success": False,
            "ticket": 0,
            "executed_price": 0,
            "executed_lot": 0,
            "error_code": code,
            "error_message": message,
            "timestamp": now,
        }
