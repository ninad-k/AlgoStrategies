using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Services.RuleMatchers;

public class LotSizeRuleMatcher : IRuleMatcher
{
    public RuleType SupportedType => RuleType.LotSize;

    public bool Matches(Trade trade, CategorizationRule rule)
    {
        if (!rule.LotSizeMin.HasValue || !rule.LotSizeMax.HasValue)
            return false;

        return trade.Volume >= rule.LotSizeMin.Value
            && trade.Volume <= rule.LotSizeMax.Value;
    }
}
