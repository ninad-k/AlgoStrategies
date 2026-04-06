using Mt5PnlDashboard.Core.Models;
using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Infrastructure.Services.RuleMatchers;

public class TimeOfDayRuleMatcher : IRuleMatcher
{
    public RuleType SupportedType => RuleType.TimeOfDay;

    public bool Matches(Trade trade, CategorizationRule rule)
    {
        if (!rule.TimeOfDayStartUtc.HasValue || !rule.TimeOfDayEndUtc.HasValue)
            return false;

        var tradeTime = trade.EntryTime.TimeOfDay;
        var start = rule.TimeOfDayStartUtc.Value;
        var end = rule.TimeOfDayEndUtc.Value;

        // Handle ranges that span midnight (e.g., 22:00 - 04:00)
        if (start <= end)
            return tradeTime >= start && tradeTime <= end;

        return tradeTime >= start || tradeTime <= end;
    }
}
