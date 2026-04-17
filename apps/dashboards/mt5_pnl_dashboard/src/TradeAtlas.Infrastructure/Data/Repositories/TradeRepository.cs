using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class TradeRepository : ITradeRepository
{
    private readonly AppDbContext _context;

    public TradeRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<Trade?> GetByIdAsync(string id, CancellationToken ct = default)
    {
        return await _context.Trades
            .Include(t => t.Account)
            .Include(t => t.Trader)
            .FirstOrDefaultAsync(t => t.Id == id, ct);
    }

    public async Task<IReadOnlyList<Trade>> GetByAccountIdAsync(string accountId, CancellationToken ct = default)
    {
        return await _context.Trades
            .Include(t => t.Account)
            .Include(t => t.Trader)
            .Where(t => t.AccountId == accountId)
            .ToListAsync(ct);
    }

    public async Task<IReadOnlyList<Trade>> GetByStatusAsync(CategorizationStatus status, CancellationToken ct = default)
    {
        return await _context.Trades
            .Include(t => t.Account)
            .Include(t => t.Trader)
            .Where(t => t.CategorizationStatus == status)
            .ToListAsync(ct);
    }

    public async Task<IReadOnlyList<Trade>> GetByOriginAsync(TradeOrigin origin, CancellationToken ct = default)
    {
        return await _context.Trades
            .Include(t => t.Account)
            .Include(t => t.Trader)
            .Where(t => t.TradeOrigin == origin)
            .ToListAsync(ct);
    }

    public async Task<IReadOnlyList<Trade>> GetByDateRangeAsync(
        DateTime start, DateTime end, string? accountId = null, CancellationToken ct = default)
    {
        var query = _context.Trades
            .Include(t => t.Account)
            .Include(t => t.Trader)
            .Where(t => t.EntryTime >= start && t.EntryTime <= end);

        if (!string.IsNullOrEmpty(accountId))
            query = query.Where(t => t.AccountId == accountId);

        return await query.ToListAsync(ct);
    }

    public async Task AddAsync(Trade trade, CancellationToken ct = default)
    {
        await _context.Trades.AddAsync(trade, ct);
    }

    public Task UpdateAsync(Trade trade, CancellationToken ct = default)
    {
        _context.Trades.Update(trade);
        return Task.CompletedTask;
    }

    public async Task<int> GetCountAsync(CancellationToken ct = default)
    {
        return await _context.Trades.CountAsync(ct);
    }
}
