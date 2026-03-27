from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Order:
    order_num: int
    symbol: str
    type: str  # 'buy' or 'sell'
    volume: float
    price: float
    sl: float = 0.0
    tp: float = 0.0
    open_time: str = ""
    state: str = "filled"
    comment: str = ""


@dataclass
class Deal:
    deal_num: int
    order_num: int
    time: str
    symbol: str
    type: str  # 'buy' or 'sell'
    direction: str  # 'in', 'out', 'balance'
    volume: float
    price: float
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    balance: float = 0.0
    comment: str = ""


@dataclass
class Position:
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    volume: float
    open_time: str
    sl: float = 0.0
    tp: float = 0.0
    order_num: int = 0
    comment: str = ""
    mfe: float = 0.0
    mae: float = 0.0


class PositionManager:
    def __init__(self, initial_balance: float):
        self._balance: float = initial_balance
        self._position: Optional[Position] = None
        self._next_order_num: int = 1
        self._next_deal_num: int = 1
        self._orders: list[Order] = []
        self._deals: list[Deal] = []
        self._closed_trades: list[dict] = []

    @property
    def has_position(self) -> bool:
        return self._position is not None

    @property
    def position_size(self) -> float:
        if self._position is None:
            return 0.0
        if self._position.direction == "long":
            return self._position.volume
        return -self._position.volume

    @property
    def all_orders(self) -> list[Order]:
        return list(self._orders)

    @property
    def all_deals(self) -> list[Deal]:
        return list(self._deals)

    @property
    def closed_trades(self) -> list[dict]:
        return list(self._closed_trades)

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def current_position(self) -> Optional[Position]:
        return self._position

    def open_position(
        self,
        time: str,
        symbol: str,
        direction: str,
        volume: float,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        commission_pct: float = 0.0,
        comment: str = "",
    ) -> Order:
        order_type = "buy" if direction == "long" else "sell"

        order = Order(
            order_num=self._next_order_num,
            symbol=symbol,
            type=order_type,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            open_time=time,
            comment=comment,
        )
        self._orders.append(order)

        commission = price * volume * commission_pct
        self._balance -= commission

        deal = Deal(
            deal_num=self._next_deal_num,
            order_num=self._next_order_num,
            time=time,
            symbol=symbol,
            type=order_type,
            direction="in",
            volume=volume,
            price=price,
            commission=commission,
            balance=self._balance,
            comment=comment,
        )
        self._deals.append(deal)

        self._position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            volume=volume,
            open_time=time,
            sl=sl,
            tp=tp,
            order_num=self._next_order_num,
            comment=comment,
        )

        self._next_order_num += 1
        self._next_deal_num += 1
        return order

    def close_position(
        self,
        time: str,
        price: float,
        volume_pct: float = 1.0,
        commission_pct: float = 0.0,
        comment: str = "",
    ) -> Optional[Deal]:
        if self._position is None:
            return None

        pos = self._position
        close_volume = pos.volume * volume_pct
        order_type = "sell" if pos.direction == "long" else "buy"

        if pos.direction == "long":
            profit = (price - pos.entry_price) * close_volume
        else:
            profit = (pos.entry_price - price) * close_volume

        commission = price * close_volume * commission_pct
        self._balance += profit - commission

        order = Order(
            order_num=self._next_order_num,
            symbol=pos.symbol,
            type=order_type,
            volume=close_volume,
            price=price,
            open_time=time,
            comment=comment,
        )
        self._orders.append(order)

        deal = Deal(
            deal_num=self._next_deal_num,
            order_num=self._next_order_num,
            time=time,
            symbol=pos.symbol,
            type=order_type,
            direction="out",
            volume=close_volume,
            price=price,
            commission=commission,
            profit=profit,
            balance=self._balance,
            comment=comment,
        )
        self._deals.append(deal)

        self._next_order_num += 1
        self._next_deal_num += 1

        if volume_pct >= 1.0:
            self._closed_trades.append(
                {
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "entry_price": pos.entry_price,
                    "exit_price": price,
                    "volume": pos.volume,
                    "open_time": pos.open_time,
                    "close_time": time,
                    "profit": profit,
                    "commission": commission + (pos.entry_price * pos.volume * commission_pct),
                    "mfe": pos.mfe,
                    "mae": pos.mae,
                    "entry_order": pos.order_num,
                    "exit_order": order.order_num,
                    "comment": pos.comment,
                }
            )
            self._position = None
        else:
            remaining = pos.volume - close_volume
            if remaining <= 1e-10:
                self._closed_trades.append(
                    {
                        "symbol": pos.symbol,
                        "direction": pos.direction,
                        "entry_price": pos.entry_price,
                        "exit_price": price,
                        "volume": pos.volume,
                        "open_time": pos.open_time,
                        "close_time": time,
                        "profit": profit,
                        "commission": commission + (pos.entry_price * close_volume * commission_pct),
                        "mfe": pos.mfe,
                        "mae": pos.mae,
                        "entry_order": pos.order_num,
                        "exit_order": order.order_num,
                        "comment": pos.comment,
                    }
                )
                self._position = None
            else:
                self._closed_trades.append(
                    {
                        "symbol": pos.symbol,
                        "direction": pos.direction,
                        "entry_price": pos.entry_price,
                        "exit_price": price,
                        "volume": close_volume,
                        "open_time": pos.open_time,
                        "close_time": time,
                        "profit": profit,
                        "commission": commission + (pos.entry_price * close_volume * commission_pct),
                        "mfe": pos.mfe,
                        "mae": pos.mae,
                        "entry_order": pos.order_num,
                        "exit_order": order.order_num,
                        "comment": pos.comment,
                    }
                )
                pos.volume = remaining

        return deal

    def update_mfe_mae(self, high: float, low: float) -> None:
        if self._position is None:
            return

        pos = self._position
        if pos.direction == "long":
            favorable = high - pos.entry_price
            adverse = pos.entry_price - low
        else:
            favorable = pos.entry_price - low
            adverse = high - pos.entry_price

        pos.mfe = max(pos.mfe, favorable)
        pos.mae = max(pos.mae, adverse)

    def check_sl_tp(
        self,
        high: float,
        low: float,
        time: str,
        commission_pct: float = 0.0,
    ) -> bool:
        if self._position is None:
            return False

        pos = self._position
        sl_hit = False
        tp_hit = False

        if pos.direction == "long":
            if pos.sl > 0 and low <= pos.sl:
                sl_hit = True
            if pos.tp > 0 and high >= pos.tp:
                tp_hit = True
        else:
            if pos.sl > 0 and high >= pos.sl:
                sl_hit = True
            if pos.tp > 0 and low <= pos.tp:
                tp_hit = True

        if sl_hit:
            self.close_position(time, pos.sl, 1.0, commission_pct, "sl_hit")
            return True
        if tp_hit:
            self.close_position(time, pos.tp, 1.0, commission_pct, "tp_hit")
            return True

        return False
