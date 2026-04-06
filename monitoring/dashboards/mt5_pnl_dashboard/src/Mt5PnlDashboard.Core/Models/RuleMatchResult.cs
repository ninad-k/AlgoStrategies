namespace Mt5PnlDashboard.Core.Models;

public class RuleMatchResult
{
    public Trade Trade { get; set; } = null!;
    public CategorizationRule? MatchedRule { get; set; }
    public string? StrategyId { get; set; }
    public string? TraderId { get; set; }
    public bool IsMatch { get; set; }

    public static RuleMatchResult Uncategorized(Trade trade) => new()
    {
        Trade = trade,
        MatchedRule = null,
        StrategyId = null,
        TraderId = null,
        IsMatch = false
    };
}
