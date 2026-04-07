using System.Text.RegularExpressions;
using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Services.RuleMatchers;

public class SymbolPatternRuleMatcher : IRuleMatcher
{
    public RuleType SupportedType => RuleType.Symbol;

    public bool Matches(Trade trade, CategorizationRule rule)
    {
        if (string.IsNullOrEmpty(rule.SymbolPattern) || string.IsNullOrEmpty(trade.Symbol))
            return false;

        return Regex.IsMatch(trade.Symbol, rule.SymbolPattern, RegexOptions.IgnoreCase);
    }
}
