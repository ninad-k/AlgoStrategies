namespace TradeAtlas.Core.Models;

public class AccountTraderAssignment
{
    public string Id { get; set; } = string.Empty;
    public string AccountId { get; set; } = string.Empty;
    public string TraderId { get; set; } = string.Empty;

    // Navigation
    public Account Account { get; set; } = null!;
    public Trader Trader { get; set; } = null!;
}
