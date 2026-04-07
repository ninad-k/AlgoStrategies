namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface ITradeDistributionRuleRepository
{
    Task<IReadOnlyList<TradeDistributionRule>> GetByAccountIdAsync(string accountId, CancellationToken ct = default);
    Task AddAsync(TradeDistributionRule rule, CancellationToken ct = default);
    Task UpdateAsync(TradeDistributionRule rule, CancellationToken ct = default);
    Task DeleteAsync(string id, CancellationToken ct = default);
}
