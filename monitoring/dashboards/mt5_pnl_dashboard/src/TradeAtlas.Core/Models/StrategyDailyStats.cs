namespace TradeAtlas.Core.Models;

public class StrategyDailyStats
{
    public int Id { get; set; }
    public string AccountId { get; set; } = string.Empty;
    public string StrategyName { get; set; } = string.Empty;
    public DateTime StatDate { get; set; }
    public int TradeCount { get; set; }
    public int WinningTrades { get; set; }
    public int LosingTrades { get; set; }
    public double TotalPnl { get; set; }
    public double? WinRate { get; set; }
    public double? ProfitFactor { get; set; }
    public double? AverageWin { get; set; }
    public double? AverageLoss { get; set; }
    public double? LargestWin { get; set; }
    public double? LargestLoss { get; set; }

    // Navigation
    public Account Account { get; set; } = null!;
}
