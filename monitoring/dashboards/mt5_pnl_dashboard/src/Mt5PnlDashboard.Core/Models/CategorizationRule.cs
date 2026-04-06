using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Core.Models;

public class CategorizationRule
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public int Priority { get; set; }
    public string? StrategyId { get; set; }
    public string? TraderId { get; set; }
    public RuleType RuleType { get; set; }
    public int? MagicNumberStart { get; set; }
    public int? MagicNumberEnd { get; set; }
    public double? LotSizeMin { get; set; }
    public double? LotSizeMax { get; set; }
    public string? CommentPattern { get; set; }
    public string? SymbolPattern { get; set; }
    public TimeSpan? TimeOfDayStartUtc { get; set; }
    public TimeSpan? TimeOfDayEndUtc { get; set; }
    public bool IsActive { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation
    public Strategy? Strategy { get; set; }
    public Trader? Trader { get; set; }
}
