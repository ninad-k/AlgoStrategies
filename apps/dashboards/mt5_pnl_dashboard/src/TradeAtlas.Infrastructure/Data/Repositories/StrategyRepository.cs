using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class StrategyRepository : IStrategyRepository
{
    private readonly AppDbContext _context;

    public StrategyRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<Strategy?> GetByIdAsync(string id, CancellationToken ct = default)
    {
        return await _context.Strategies.FirstOrDefaultAsync(s => s.Id == id, ct);
    }

    public async Task<IReadOnlyList<Strategy>> GetAllAsync(CancellationToken ct = default)
    {
        return await _context.Strategies.ToListAsync(ct);
    }

    public async Task<Strategy?> GetByNameAsync(string name, CancellationToken ct = default)
    {
        return await _context.Strategies.FirstOrDefaultAsync(s => s.Name == name, ct);
    }

    public async Task AddAsync(Strategy strategy, CancellationToken ct = default)
    {
        await _context.Strategies.AddAsync(strategy, ct);
    }

    public Task UpdateAsync(Strategy strategy, CancellationToken ct = default)
    {
        _context.Strategies.Update(strategy);
        return Task.CompletedTask;
    }

    public async Task DeleteAsync(string id, CancellationToken ct = default)
    {
        var strategy = await _context.Strategies.FindAsync(new object[] { id }, ct);
        if (strategy is not null)
            _context.Strategies.Remove(strategy);
    }
}
