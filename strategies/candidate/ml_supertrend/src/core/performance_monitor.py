# Performance Monitor
# Author: Ninad
#
# Trade history analysis and charting: equity curves, win rate by hour,
# P&L distribution, and trade duration vs profit scatter.

import json
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np


class PerformanceMonitor:
    def __init__(self, trades_file: str = 'trades.json'):
        self.trades_file = trades_file
        self.trades = self._load_trades()

    def _load_trades(self) -> list:
        if not os.path.exists(self.trades_file):
            return []
        with open(self.trades_file, 'r') as f:
            return json.load(f)

    def calculate_metrics(self) -> dict:
        if not self.trades:
            return {}

        profits = [t['profit'] for t in self.trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]

        total_profit = sum(wins) if wins else 0
        total_loss = abs(sum(losses)) if losses else 0

        return {
            "total_trades": len(self.trades),
            "win_rate": (len(wins) / len(self.trades)) * 100 if self.trades else 0,
            "profit_factor": total_profit / total_loss if total_loss > 0 else float('inf'),
            "avg_win": np.mean(wins) if wins else 0,
            "avg_loss": np.mean(np.abs(losses)) if losses else 0,
            "risk_reward": (np.mean(wins) / np.mean(np.abs(losses))) if wins and losses else 0,
            "max_consecutive_wins": self._max_consecutive(profits, positive=True),
            "max_consecutive_losses": self._max_consecutive(profits, positive=False),
            "net_profit": sum(profits),
        }

    @staticmethod
    def _max_consecutive(profits: list, positive: bool) -> int:
        max_streak = 0
        current = 0
        for p in profits:
            if (positive and p > 0) or (not positive and p < 0):
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    def generate_charts(self, save_path: str = None):
        """Create a 4-panel figure: equity curve, hourly win rate, P&L histogram, duration vs profit."""
        if not self.trades:
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Trading Performance Report', fontsize=14)

        # Equity curve
        equity = np.cumsum([t['profit'] for t in self.trades])
        axes[0, 0].plot(equity, linewidth=1.5)
        axes[0, 0].set_title('Equity Curve')
        axes[0, 0].set_xlabel('Trade #')
        axes[0, 0].set_ylabel('Cumulative P&L')
        axes[0, 0].grid(True, alpha=0.3)

        # Win rate by hour
        hourly = {}
        for t in self.trades:
            if 'entry_time' in t:
                hour = datetime.strptime(t['entry_time'], '%Y-%m-%d %H:%M:%S').hour
                hourly.setdefault(hour, []).append(t['profit'])
        if hourly:
            hours = sorted(hourly.keys())
            rates = [(sum(1 for p in hourly[h] if p > 0) / len(hourly[h])) * 100 for h in hours]
            axes[0, 1].bar(hours, rates, color='steelblue')
            axes[0, 1].set_title('Win Rate by Hour')
            axes[0, 1].set_xlabel('Hour (UTC)')
            axes[0, 1].set_ylabel('Win Rate %')

        # P&L distribution
        profits = [t['profit'] for t in self.trades]
        axes[1, 0].hist(profits, bins=30, edgecolor='black', alpha=0.7)
        axes[1, 0].axvline(x=0, color='red', linestyle='--')
        axes[1, 0].set_title('P&L Distribution')
        axes[1, 0].set_xlabel('Profit/Loss')

        # Duration vs profit
        durations = []
        pnls = []
        for t in self.trades:
            if 'entry_time' in t and 'exit_time' in t:
                entry = datetime.strptime(t['entry_time'], '%Y-%m-%d %H:%M:%S')
                exit_ = datetime.strptime(t['exit_time'], '%Y-%m-%d %H:%M:%S')
                durations.append((exit_ - entry).total_seconds() / 3600)
                pnls.append(t['profit'])
        if durations:
            colors = ['green' if p > 0 else 'red' for p in pnls]
            axes[1, 1].scatter(durations, pnls, c=colors, alpha=0.6, s=30)
            axes[1, 1].axhline(y=0, color='gray', linestyle='--')
            axes[1, 1].set_title('Duration vs Profit')
            axes[1, 1].set_xlabel('Duration (hours)')
            axes[1, 1].set_ylabel('Profit/Loss')

        plt.tight_layout()

        if save_path is None:
            save_path = f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(save_path, dpi=150)
        plt.close()
        return save_path

    def generate_report(self, days: int = 30):
        """Filter to recent trades and print metrics + save chart."""
        cutoff = datetime.now() - timedelta(days=days)
        self.trades = [
            t for t in self.trades
            if 'entry_time' in t and datetime.strptime(t['entry_time'], '%Y-%m-%d %H:%M:%S') >= cutoff
        ]

        metrics = self.calculate_metrics()
        if metrics:
            print(f"\n{'=' * 40}")
            print(f"  Performance Report (last {days} days)")
            print(f"{'=' * 40}")
            for key, value in metrics.items():
                print(f"  {key:.<30} {value:.2f}" if isinstance(value, float) else f"  {key:.<30} {value}")
            print(f"{'=' * 40}\n")

        self.generate_charts()
