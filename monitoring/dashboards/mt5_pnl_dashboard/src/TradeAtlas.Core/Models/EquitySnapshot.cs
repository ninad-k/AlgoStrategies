namespace TradeAtlas.Core.Models;

public class EquitySnapshot
{
    public int Id { get; set; }
    public string AccountId { get; set; } = string.Empty;
    public DateTime SnapshotDate { get; set; }
    public double Balance { get; set; }
    public double Equity { get; set; }
    public double? FreeMargin { get; set; }
    public double? MarginLevel { get; set; }
    public int OpenTradeCount { get; set; }
    public int ClosedTradeCount { get; set; }
    public double DailyPnl { get; set; }
    public double DrawdownAbsolute { get; set; }
    public double DrawdownPercent { get; set; }

    // Navigation
    public Account Account { get; set; } = null!;
}
