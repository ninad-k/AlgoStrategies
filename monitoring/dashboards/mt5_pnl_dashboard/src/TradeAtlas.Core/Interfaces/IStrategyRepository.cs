namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface IStrategyRepository
{
    Task<Strategy?> GetByIdAsync(string id, CancellationToken ct = default);
    Task<IReadOnlyList<Strategy>> GetAllAsync(CancellationToken ct = default);
    Task<Strategy?> GetByNameAsync(string name, CancellationToken ct = default);
    Task AddAsync(Strategy strategy, CancellationToken ct = default);
    Task UpdateAsync(Strategy strategy, CancellationToken ct = default);
    Task DeleteAsync(string id, CancellationToken ct = default);
}
