namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface ITraderRepository
{
    Task<Trader?> GetByIdAsync(string id, CancellationToken ct = default);
    Task<IReadOnlyList<Trader>> GetAllAsync(CancellationToken ct = default);
    Task<IReadOnlyList<Trader>> GetActiveAsync(CancellationToken ct = default);
    Task AddAsync(Trader trader, CancellationToken ct = default);
    Task UpdateAsync(Trader trader, CancellationToken ct = default);
    Task DeleteAsync(string id, CancellationToken ct = default);
}
