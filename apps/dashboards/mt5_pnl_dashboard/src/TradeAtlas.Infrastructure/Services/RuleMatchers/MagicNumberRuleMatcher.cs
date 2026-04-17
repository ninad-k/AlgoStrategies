using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Services.RuleMatchers;

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
