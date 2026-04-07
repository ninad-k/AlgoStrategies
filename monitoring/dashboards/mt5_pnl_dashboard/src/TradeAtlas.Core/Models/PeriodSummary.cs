using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Core.Models;

public class PeriodSummary
{
    public int Id { get; set; }
    public string AccountId { get; set; } = string.Empty;
    public PeriodType PeriodType { get; set; }
    public DateTime PeriodStart { get; set; }
    public DateTime PeriodEnd { get; set; }
    public double? TotalPnl { get; set; }
    public int? TradeCount { get; set; }
    public double? WinRate { get; set; }
    public double? ProfitFactor { get; set; }
    public double? MaxDrawdownPct { get; set; }
    public double? SharpeRatio { get; set; }
    public double? SortinoRatio { get; set; }
    public double? CalmarRatio { get; set; }
    public double? RecoveryFactor { get; set; }
    public double? Expectancy { get; set; }
}
