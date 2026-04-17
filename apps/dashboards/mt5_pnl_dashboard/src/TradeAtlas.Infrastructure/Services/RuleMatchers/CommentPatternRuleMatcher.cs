using System.Text.RegularExpressions;
using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Services.RuleMatchers;

public class CommentPatternRuleMatcher : IRuleMatcher
{
    public RuleType SupportedType => RuleType.Comment;

    public bool Matches(Trade trade, CategorizationRule rule)
    {
        if (string.IsNullOrEmpty(rule.CommentPattern) || string.IsNullOrEmpty(trade.OrderComment))
            return false;

        return Regex.IsMatch(trade.OrderComment, rule.CommentPattern, RegexOptions.IgnoreCase);
    }
}
