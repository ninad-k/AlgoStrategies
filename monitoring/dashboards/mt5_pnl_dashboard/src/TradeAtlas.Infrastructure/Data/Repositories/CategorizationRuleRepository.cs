using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class CategorizationRuleRepository : ICategorizationRuleRepository
{
    private readonly AppDbContext _context;

    public CategorizationRuleRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<IReadOnlyList<CategorizationRule>> GetAllActiveAsync(CancellationToken ct = default)
    {
        return await _context.CategorizationRules
            .Include(r => r.Strategy)
            .Include(r => r.Trader)
            .Where(r => r.IsActive)
            .OrderBy(r => r.Priority)
            .ToListAsync(ct);
    }

    public async Task<CategorizationRule?> GetByIdAsync(string id, CancellationToken ct = default)
    {
        return await _context.CategorizationRules
            .Include(r => r.Strategy)
            .Include(r => r.Trader)
            .FirstOrDefaultAsync(r => r.Id == id, ct);
    }

    public async Task AddAsync(CategorizationRule rule, CancellationToken ct = default)
    {
        await _context.CategorizationRules.AddAsync(rule, ct);
    }

    public Task UpdateAsync(CategorizationRule rule, CancellationToken ct = default)
    {
        _context.CategorizationRules.Update(rule);
        return Task.CompletedTask;
    }

    public async Task DeleteAsync(string id, CancellationToken ct = default)
    {
        var rule = await _context.CategorizationRules.FindAsync(new object[] { id }, ct);
        if (rule is not null)
            _context.CategorizationRules.Remove(rule);
    }
}
