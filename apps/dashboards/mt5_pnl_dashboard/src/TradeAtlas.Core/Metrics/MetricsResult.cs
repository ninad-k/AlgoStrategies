namespace TradeAtlas.Core.Metrics;

public class MetricsResult
{
    public double TotalPnl { get; set; }
    public double NetPnl { get; set; }
    public double WinRate { get; set; }
    public double ProfitFactor { get; set; }
    public double SharpeRatio { get; set; }
    public double SortinoRatio { get; set; }
    public double CalmarRatio { get; set; }
    public double MaxDrawdownPercent { get; set; }
    public double MaxDrawdownAbsolute { get; set; }
    public double RecoveryFactor { get; set; }
    public double Expectancy { get; set; }
    public double TotalTrades { get; set; }
    public double WinningTrades { get; set; }
    public double LosingTrades { get; set; }
    public double AverageWin { get; set; }
    public double AverageLoss { get; set; }
    public double LargestWin { get; set; }
    public double LargestLoss { get; set; }
    public double AverageHoldingMinutes { get; set; }
    public double ConsecutiveWins { get; set; }
    public double ConsecutiveLosses { get; set; }
}
