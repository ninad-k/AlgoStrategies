namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

public interface ITradeRepository
{
    Task<Trade?> GetByIdAsync(string id, CancellationToken ct = default);
    Task<IReadOnlyList<Trade>> GetByAccountIdAsync(string accountId, CancellationToken ct = default);
    Task<IReadOnlyList<Trade>> GetByStatusAsync(CategorizationStatus status, CancellationToken ct = default);
    Task<IReadOnlyList<Trade>> GetByOriginAsync(TradeOrigin origin, CancellationToken ct = default);
    Task<IReadOnlyList<Trade>> GetByDateRangeAsync(DateTime start, DateTime end, string? accountId = null, CancellationToken ct = default);
    Task AddAsync(Trade trade, CancellationToken ct = default);
    Task UpdateAsync(Trade trade, CancellationToken ct = default);
    Task<int> GetCountAsync(CancellationToken ct = default);
}
