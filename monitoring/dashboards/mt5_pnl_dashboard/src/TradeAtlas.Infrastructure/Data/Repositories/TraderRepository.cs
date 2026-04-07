using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class TraderRepository : ITraderRepository
{
    private readonly AppDbContext _context;

    public TraderRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<Trader?> GetByIdAsync(string id, CancellationToken ct = default)
    {
        return await _context.Traders.FirstOrDefaultAsync(t => t.Id == id, ct);
    }

    public async Task<IReadOnlyList<Trader>> GetAllAsync(CancellationToken ct = default)
    {
        return await _context.Traders.ToListAsync(ct);
    }

    public async Task<IReadOnlyList<Trader>> GetActiveAsync(CancellationToken ct = default)
    {
        return await _context.Traders
            .Where(t => t.IsActive)
            .ToListAsync(ct);
    }

    public async Task AddAsync(Trader trader, CancellationToken ct = default)
    {
        await _context.Traders.AddAsync(trader, ct);
    }

    public Task UpdateAsync(Trader trader, CancellationToken ct = default)
    {
        _context.Traders.Update(trader);
        return Task.CompletedTask;
    }

    public async Task DeleteAsync(string id, CancellationToken ct = default)
    {
        var trader = await _context.Traders.FindAsync(new object[] { id }, ct);
        if (trader is not null)
            _context.Traders.Remove(trader);
    }
}
