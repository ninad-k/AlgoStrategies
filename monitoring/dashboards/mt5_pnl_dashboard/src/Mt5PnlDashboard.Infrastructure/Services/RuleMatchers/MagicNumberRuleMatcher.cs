using Mt5PnlDashboard.Core.Models;
using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Infrastructure.Services.RuleMatchers;

public class MagicNumberRuleMatcher : IRuleMatcher
{
    public RuleType SupportedType => RuleType.MagicNumber;

    public bool Matches(Trade trade, CategorizationRule rule)
    {
        if (!rule.MagicNumberStart.HasValue || !rule.MagicNumberEnd.HasValue)
            return false;

        return trade.MagicNumber >= rule.MagicNumberStart.Value
            && trade.MagicNumber <= rule.MagicNumberEnd.Value;
    }
}
