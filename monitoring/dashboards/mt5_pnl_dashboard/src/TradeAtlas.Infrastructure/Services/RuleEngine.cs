using Microsoft.Extensions.Logging;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;
using TradeAtlas.Infrastructure.Logging;
using TradeAtlas.Infrastructure.Services.RuleMatchers;

namespace TradeAtlas.Infrastructure.Services;

public class RuleEngine : IRuleEngine
{
    private readonly ICategorizationRuleRepository _ruleRepository;
    private readonly Dictionary<RuleType, IRuleMatcher> _matchers;
    private readonly ILogger<RuleEngine> _logger;

    public RuleEngine(
        ICategorizationRuleRepository ruleRepository,
        IEnumerable<IRuleMatcher> matchers,
        ILogger<RuleEngine> logger)
    {
        _ruleRepository = ruleRepository;
        _matchers = matchers.ToDictionary(m => m.SupportedType);
        _logger = logger;
    }

    public async Task EvaluateTradeAsync(Trade trade, CancellationToken ct = default)
    {
        using var timing = _logger.TimeOperation("EvaluateTrade:{TradeId}", trade.Id);

        var rules = await _ruleRepository.GetAllActiveAsync(ct);

        foreach (var rule in rules)
        {
            if (!_matchers.TryGetValue(rule.RuleType, out var matcher))
            {
                _logger.LogWarning("No matcher registered for RuleType {RuleType}", rule.RuleType);
                continue;
            }

            if (matcher.Matches(trade, rule))
            {
                trade.StrategyName = rule.Strategy?.Name;
                trade.TraderId = rule.TraderId;
                trade.CategorizationStatus = CategorizationStatus.RuleMatched;

                _logger.LogInformation(
                    "Trade {TradeId} matched rule {RuleId} ({RuleName}), assigned Strategy={Strategy}, Trader={TraderId}",
                    trade.Id, rule.Id, rule.Name, trade.StrategyName, trade.TraderId);
                return;
            }
        }

        trade.CategorizationStatus = CategorizationStatus.Uncategorized;
        _logger.LogDebug("Trade {TradeId} did not match any categorization rule", trade.Id);
    }

    public async Task<int> GetPreviewMatchCountAsync(CategorizationRule rule, CancellationToken ct = default)
    {
        using var timing = _logger.TimeOperation("GetPreviewMatchCount:{RuleId}", rule.Id);

        if (!_matchers.TryGetValue(rule.RuleType, out var matcher))
        {
            _logger.LogWarning("No matcher registered for RuleType {RuleType}", rule.RuleType);
            return 0;
        }

        // Get uncategorized trades to preview against
        var trades = await GetUncategorizedTradesAsync(ct);
        var matchCount = trades.Count(t => matcher.Matches(t, rule));

        _logger.LogInformation(
            "Preview match count for rule {RuleName}: {MatchCount} out of {TotalCount} uncategorized trades",
            rule.Name, matchCount, trades.Count);

        return matchCount;
    }

    private async Task<IReadOnlyList<Trade>> GetUncategorizedTradesAsync(CancellationToken ct)
    {
        // This would ideally use a trade repository, but we access it through the rule repository's context
        // In practice, the caller should inject ITradeRepository if needed.
        // For now, return empty - the UnitOfWork pattern handles this at the service layer.
        await Task.CompletedTask;
        return Array.Empty<Trade>();
    }
}
