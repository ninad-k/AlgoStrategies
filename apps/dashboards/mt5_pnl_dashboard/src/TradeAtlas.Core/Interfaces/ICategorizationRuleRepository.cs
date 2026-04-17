namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface ICategorizationRuleRepository
{
    Task<IReadOnlyList<CategorizationRule>> GetAllActiveAsync(CancellationToken ct = default);
    Task<CategorizationRule?> GetByIdAsync(string id, CancellationToken ct = default);
    Task AddAsync(CategorizationRule rule, CancellationToken ct = default);
    Task UpdateAsync(CategorizationRule rule, CancellationToken ct = default);
    Task DeleteAsync(string id, CancellationToken ct = default);
}
