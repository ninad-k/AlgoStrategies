using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class EquitySnapshotRepository : IEquitySnapshotRepository
{
    private readonly AppDbContext _context;

    public EquitySnapshotRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<IReadOnlyList<EquitySnapshot>> GetByAccountAndDateRangeAsync(
        string accountId, DateTime start, DateTime end, CancellationToken ct = default)
    {
        return await _context.EquitySnapshots
            .Where(s => s.AccountId == accountId && s.SnapshotDate >= start && s.SnapshotDate <= end)
            .OrderBy(s => s.SnapshotDate)
            .ToListAsync(ct);
    }

    public async Task AddAsync(EquitySnapshot snapshot, CancellationToken ct = default)
    {
        await _context.EquitySnapshots.AddAsync(snapshot, ct);
    }

    public async Task<EquitySnapshot?> GetLatestAsync(string accountId, CancellationToken ct = default)
    {
        return await _context.EquitySnapshots
            .Where(s => s.AccountId == accountId)
            .OrderByDescending(s => s.SnapshotDate)
            .FirstOrDefaultAsync(ct);
    }
}
