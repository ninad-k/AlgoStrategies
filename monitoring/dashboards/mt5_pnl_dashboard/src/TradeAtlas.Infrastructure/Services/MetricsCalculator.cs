using Microsoft.Extensions.Logging;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Metrics;
using TradeAtlas.Core.Models;
using TradeAtlas.Infrastructure.Logging;

namespace TradeAtlas.Infrastructure.Services;

public class MetricsCalculator : IMetricsCalculator
{
    private readonly ILogger<MetricsCalculator> _logger;

    public MetricsCalculator(ILogger<MetricsCalculator> logger)
    {
        _logger = logger;
    }

    public Task<MetricsResult> CalculateAsync(IEnumerable<Trade> trades, CancellationToken ct = default)
    {
        using var timing = _logger.TimeOperation("CalculateMetrics");

        var tradeList = trades.Where(t => t.ProfitLoss.HasValue && t.ExitTime.HasValue).ToList();
        var result = new MetricsResult();

        if (tradeList.Count == 0)
        {
            _logger.LogInformation("No closed trades provided for metrics calculation");
            return Task.FromResult(result);
        }

        var pnls = tradeList.Select(t => t.ProfitLoss!.Value).ToList();
        var winners = pnls.Where(p => p > 0).ToList();
        var losers = pnls.Where(p => p < 0).ToList();

        result.TotalTrades = tradeList.Count;
        result.WinningTrades = winners.Count;
        result.LosingTrades = losers.Count;
        result.TotalPnl = pnls.Sum();
        result.NetPnl = tradeList.Sum(t => t.ProfitLoss!.Value + t.Commission + t.Swap);

        // Win Rate
        result.WinRate = winners.Count / (double)tradeList.Count;

        // Average Win / Loss
        result.AverageWin = winners.Count > 0 ? winners.Average() : 0;
        result.AverageLoss = losers.Count > 0 ? losers.Average() : 0;
        result.LargestWin = winners.Count > 0 ? winners.Max() : 0;
        result.LargestLoss = losers.Count > 0 ? losers.Min() : 0;

        // Profit Factor
        var grossProfit = winners.Sum();
        var grossLoss = Math.Abs(losers.Sum());
        result.ProfitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? double.MaxValue : 0;

        // Expectancy
        var lossRate = losers.Count / (double)tradeList.Count;
        result.Expectancy = (result.WinRate * result.AverageWin) - (lossRate * Math.Abs(result.AverageLoss));

        // Average Holding Time
        result.AverageHoldingMinutes = tradeList
            .Where(t => t.HoldingTimeMinutes.HasValue)
            .Select(t => t.HoldingTimeMinutes!.Value)
            .DefaultIfEmpty(0)
            .Average();

        // Daily returns for Sharpe / Sortino / Calmar
        var dailyReturns = CalculateDailyReturns(tradeList);

        if (dailyReturns.Count > 1)
        {
            var meanReturn = dailyReturns.Average();
            var stdDev = StandardDeviation(dailyReturns);
            var downsideDev = DownsideDeviation(dailyReturns);

            // Sharpe Ratio (annualized)
            result.SharpeRatio = stdDev > 0 ? (meanReturn / stdDev) * Math.Sqrt(252) : 0;

            // Sortino Ratio (annualized)
            result.SortinoRatio = downsideDev > 0 ? (meanReturn / downsideDev) * Math.Sqrt(252) : 0;
        }

        // Max Drawdown & Equity Curve
        CalculateDrawdown(pnls, out var maxDrawdownAbs, out var maxDrawdownPct);
        result.MaxDrawdownAbsolute = maxDrawdownAbs;
        result.MaxDrawdownPercent = maxDrawdownPct;

        // Calmar Ratio
        if (dailyReturns.Count > 0 && result.MaxDrawdownPercent > 0)
        {
            var totalDays = (tradeList.Max(t => t.ExitTime!.Value) - tradeList.Min(t => t.EntryTime)).TotalDays;
            var annualizedReturn = totalDays > 0 ? (result.TotalPnl / totalDays) * 365 : 0;
            result.CalmarRatio = annualizedReturn / result.MaxDrawdownAbsolute;
        }

        // Recovery Factor
        result.RecoveryFactor = result.MaxDrawdownAbsolute > 0
            ? result.TotalPnl / result.MaxDrawdownAbsolute
            : 0;

        // Consecutive Wins / Losses
        CalculateConsecutive(pnls, out var maxConsecWins, out var maxConsecLosses);
        result.ConsecutiveWins = maxConsecWins;
        result.ConsecutiveLosses = maxConsecLosses;

        _logger.LogInformation(
            "Metrics calculated: {TradeCount} trades, WinRate={WinRate:P2}, PF={ProfitFactor:F2}, Sharpe={Sharpe:F2}",
            result.TotalTrades, result.WinRate, result.ProfitFactor, result.SharpeRatio);

        return Task.FromResult(result);
    }

    private static List<double> CalculateDailyReturns(List<Trade> trades)
    {
        return trades
            .GroupBy(t => t.ExitTime!.Value.Date)
            .OrderBy(g => g.Key)
            .Select(g => g.Sum(t => t.ProfitLoss!.Value))
            .ToList();
    }

    private static double StandardDeviation(List<double> values)
    {
        if (values.Count < 2) return 0;
        var mean = values.Average();
        var sumSquares = values.Sum(v => (v - mean) * (v - mean));
        return Math.Sqrt(sumSquares / (values.Count - 1));
    }

    private static double DownsideDeviation(List<double> values)
    {
        if (values.Count < 2) return 0;
        var negatives = values.Where(v => v < 0).ToList();
        if (negatives.Count == 0) return 0;
        var sumSquares = negatives.Sum(v => v * v);
        return Math.Sqrt(sumSquares / (values.Count - 1));
    }

    private static void CalculateDrawdown(List<double> pnls, out double maxDrawdownAbs, out double maxDrawdownPct)
    {
        maxDrawdownAbs = 0;
        maxDrawdownPct = 0;

        double cumulativePnl = 0;
        double peak = 0;

        foreach (var pnl in pnls)
        {
            cumulativePnl += pnl;
            if (cumulativePnl > peak)
                peak = cumulativePnl;

            var drawdown = peak - cumulativePnl;
            if (drawdown > maxDrawdownAbs)
            {
                maxDrawdownAbs = drawdown;
                maxDrawdownPct = peak > 0 ? drawdown / peak * 100 : 0;
            }
        }
    }

    private static void CalculateConsecutive(List<double> pnls, out int maxWins, out int maxLosses)
    {
        maxWins = 0;
        maxLosses = 0;
        int currentWins = 0;
        int currentLosses = 0;

        foreach (var pnl in pnls)
        {
            if (pnl > 0)
            {
                currentWins++;
                currentLosses = 0;
                if (currentWins > maxWins) maxWins = currentWins;
            }
            else if (pnl < 0)
            {
                currentLosses++;
                currentWins = 0;
                if (currentLosses > maxLosses) maxLosses = currentLosses;
            }
            else
            {
                currentWins = 0;
                currentLosses = 0;
            }
        }
    }
}
