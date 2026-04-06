namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface ITradeDistributionService
{
    Task DistributeTradeAsync(Trade trade, string accountId, CancellationToken ct = default);
}
