using Microsoft.EntityFrameworkCore;
using Mt5PnlDashboard.Core.Interfaces;
using Mt5PnlDashboard.Core.Models;

namespace Mt5PnlDashboard.Infrastructure.Data.Repositories;

public class TradeDistributionRuleRepository : ITradeDistributionRuleRepository
{
    private readonly AppDbContext _context;

    public TradeDistributionRuleRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<IReadOnlyList<TradeDistributionRule>> GetByAccountIdAsync(string accountId, CancellationToken ct = default)
    {
        return await _context.TradeDistributionRules
            .Include(r => r.Account)
            .Include(r => r.Trader)
            .Where(r => r.AccountId == accountId)
            .OrderBy(r => r.Priority)
            .ToListAsync(ct);
    }

    public async Task AddAsync(TradeDistributionRule rule, CancellationToken ct = default)
    {
        await _context.TradeDistributionRules.AddAsync(rule, ct);
    }

    public Task UpdateAsync(TradeDistributionRule rule, CancellationToken ct = default)
    {
        _context.TradeDistributionRules.Update(rule);
        return Task.CompletedTask;
    }

    public async Task DeleteAsync(string id, CancellationToken ct = default)
    {
        var rule = await _context.TradeDistributionRules.FindAsync(new object[] { id }, ct);
        if (rule is not null)
            _context.TradeDistributionRules.Remove(rule);
    }
}
