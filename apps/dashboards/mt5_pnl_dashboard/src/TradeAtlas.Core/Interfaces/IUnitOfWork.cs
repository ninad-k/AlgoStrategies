namespace TradeAtlas.Core.Interfaces;

public interface IUnitOfWork : IDisposable
{
    ITradeRepository Trades { get; }
    IAccountRepository Accounts { get; }
    IStrategyRepository Strategies { get; }
    ITraderRepository Traders { get; }
    ICategorizationRuleRepository CategorizationRules { get; }
    ITradeDistributionRuleRepository TradeDistributionRules { get; }
    IEquitySnapshotRepository EquitySnapshots { get; }
    Task<int> SaveChangesAsync(CancellationToken ct = default);
}
