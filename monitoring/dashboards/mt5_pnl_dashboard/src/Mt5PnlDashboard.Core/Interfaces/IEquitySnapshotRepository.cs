namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface IEquitySnapshotRepository
{
    Task<IReadOnlyList<EquitySnapshot>> GetByAccountAndDateRangeAsync(string accountId, DateTime start, DateTime end, CancellationToken ct = default);
    Task AddAsync(EquitySnapshot snapshot, CancellationToken ct = default);
    Task<EquitySnapshot?> GetLatestAsync(string accountId, CancellationToken ct = default);
}
