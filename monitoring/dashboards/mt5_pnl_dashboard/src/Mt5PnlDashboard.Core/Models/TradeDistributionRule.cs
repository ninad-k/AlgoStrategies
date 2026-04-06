using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Core.Models;

public class TradeDistributionRule
{
    public string Id { get; set; } = string.Empty;
    public string AccountId { get; set; } = string.Empty;
    public string TraderId { get; set; } = string.Empty;
    public int Priority { get; set; }
    public RuleType RuleType { get; set; }
    public int? MagicNumberStart { get; set; }
    public int? MagicNumberEnd { get; set; }
    public string? LotSizePattern { get; set; }
    public string? CommentPattern { get; set; }
    public string? SymbolPattern { get; set; }
    public TimeSpan? TimeOfDayStartUtc { get; set; }
    public TimeSpan? TimeOfDayEndUtc { get; set; }
    public bool IsActive { get; set; }
    public DateTime CreatedAt { get; set; }

    // Navigation
    public Account Account { get; set; } = null!;
    public Trader Trader { get; set; } = null!;
}
