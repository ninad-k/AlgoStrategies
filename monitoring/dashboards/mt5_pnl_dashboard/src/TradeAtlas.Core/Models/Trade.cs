using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Core.Models;

public class Trade
{
    public string Id { get; set; } = string.Empty;
    public string AccountId { get; set; } = string.Empty;
    public long Ticket { get; set; }
    public long DealEntryTicket { get; set; }
    public long DealExitTicket { get; set; }
    public string Symbol { get; set; } = string.Empty;
    public TradeDirection Direction { get; set; }
    public int MagicNumber { get; set; }
    public TradeOrigin TradeOrigin { get; set; }
    public string? StrategyName { get; set; }
    public string? TraderId { get; set; }
    public CategorizationStatus CategorizationStatus { get; set; }
    public string? OrderComment { get; set; }
    public DateTime EntryTime { get; set; }
    public DateTime? ExitTime { get; set; }
    public double EntryPrice { get; set; }
    public double? ExitPrice { get; set; }
    public double Volume { get; set; }
    public double? ProfitLoss { get; set; }
    public double Commission { get; set; }
    public double Swap { get; set; }
    public double? StopLoss { get; set; }
    public double? TakeProfit { get; set; }
    public TradeStatus Status { get; set; }
    public bool IsOpen { get; set; }
    public double? Mfe { get; set; }
    public double? Mae { get; set; }
    public double? HoldingTimeMinutes { get; set; }
    public int AccountLogin { get; set; }
    public string? AccountServer { get; set; }
    public string? AccountName { get; set; }
    public string? AccountCurrency { get; set; }

    // Navigation
    public Account Account { get; set; } = null!;
    public Trader? Trader { get; set; }
}
