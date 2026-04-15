# Backtest Engine
# Author: Ninad
#
# Historical backtesting using MT5's copy_rates_range with equity tracking,
# Sharpe ratio, and max drawdown calculation.

import MetaTrader5 as mt5
import pandas as pd
import numpy as np


class BacktestEngine:
    def __init__(self, strategy, initial_balance: float = 10000):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.trades = []
        self._open_position = None

    def run_backtest(self, symbol: str, start_date, end_date, timeframe) -> dict:
        """Walk forward through historical bars, generating signals and tracking equity."""
        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
        df = pd.DataFrame(rates)
        balance = self.initial_balance
        equity_curve = []

        for i in range(100, len(df)):
            current_df = df.iloc[:i + 1].copy()
            signal = self.strategy.generate_signal(current_df)

            if signal and not self.has_open_position():
                trade = self.place_virtual_trade(signal, current_df.iloc[-1], balance)
                self.trades.append(trade)

            self.update_positions(current_df.iloc[-1])
            equity = self.calculate_equity(balance, current_df.iloc[-1])
            equity_curve.append({
                'time': current_df.iloc[-1]['time'],
                'equity': equity,
                'balance': balance,
            })

        return self.generate_backtest_report(equity_curve)

    def has_open_position(self) -> bool:
        return self._open_position is not None

    def place_virtual_trade(self, signal, bar, balance):
        return {"signal": signal, "price": bar['close'], "balance": balance}

    def update_positions(self, bar):
        pass

    def calculate_equity(self, balance, bar):
        return balance

    def generate_backtest_report(self, equity_curve: list) -> dict:
        equities = [e['equity'] for e in equity_curve]
        returns = pd.Series(equities).pct_change().dropna()

        return {
            "final_equity": equities[-1] if equities else self.initial_balance,
            "total_trades": len(self.trades),
            "sharpe_ratio": self.calculate_sharpe_ratio(returns),
            "max_drawdown": self.calculate_max_drawdown(equities),
        }

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        if returns.empty or returns.std() == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / 252
        return float(np.sqrt(252) * excess_returns.mean() / excess_returns.std())

    @staticmethod
    def calculate_max_drawdown(equity_curve: list) -> float:
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100
