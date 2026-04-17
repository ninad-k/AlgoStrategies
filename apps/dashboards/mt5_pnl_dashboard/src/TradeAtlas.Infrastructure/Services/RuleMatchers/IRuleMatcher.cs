using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Services.RuleMatchers;

public interface IRuleMatcher
{
    RuleType SupportedType { get; }
    bool Matches(Trade trade, CategorizationRule rule);
}
