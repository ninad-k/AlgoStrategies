using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Core.Models;

public class LivePosition
{
    public long Ticket { get; set; }
    public string Symbol { get; set; } = string.Empty;
    public TradeDirection Direction { get; set; }
    public int MagicNumber { get; set; }
    public DateTime OpenTime { get; set; }
    public double OpenPrice { get; set; }
    public double CurrentPrice { get; set; }
    public double Volume { get; set; }
    public double UnrealizedPnl { get; set; }
    public double Commission { get; set; }
    public double Swap { get; set; }
    public double? StopLoss { get; set; }
    public double? TakeProfit { get; set; }
    public string? OrderComment { get; set; }
    public int AccountLogin { get; set; }
}
