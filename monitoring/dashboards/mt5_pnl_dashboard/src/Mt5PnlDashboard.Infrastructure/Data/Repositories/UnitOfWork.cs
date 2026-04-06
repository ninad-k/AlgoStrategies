using Mt5PnlDashboard.Core.Interfaces;

namespace Mt5PnlDashboard.Infrastructure.Data.Repositories;

public class UnitOfWork : IUnitOfWork
{
    private readonly AppDbContext _context;

    private ITradeRepository? _trades;
    private IAccountRepository? _accounts;
    private IStrategyRepository? _strategies;
    private ITraderRepository? _traders;
    private ICategorizationRuleRepository? _categorizationRules;
    private ITradeDistributionRuleRepository? _tradeDistributionRules;
    private IEquitySnapshotRepository? _equitySnapshots;

    public UnitOfWork(AppDbContext context)
    {
        _context = context;
    }

    public ITradeRepository Trades =>
        _trades ??= new TradeRepository(_context);

    public IAccountRepository Accounts =>
        _accounts ??= new AccountRepository(_context);

    public IStrategyRepository Strategies =>
        _strategies ??= new StrategyRepository(_context);

    public ITraderRepository Traders =>
        _traders ??= new TraderRepository(_context);

    public ICategorizationRuleRepository CategorizationRules =>
        _categorizationRules ??= new CategorizationRuleRepository(_context);

    public ITradeDistributionRuleRepository TradeDistributionRules =>
        _tradeDistributionRules ??= new TradeDistributionRuleRepository(_context);

    public IEquitySnapshotRepository EquitySnapshots =>
        _equitySnapshots ??= new EquitySnapshotRepository(_context);

    public async Task<int> SaveChangesAsync(CancellationToken ct = default)
    {
        return await _context.SaveChangesAsync(ct);
    }

    public void Dispose()
    {
        _context.Dispose();
        GC.SuppressFinalize(this);
    }
}
