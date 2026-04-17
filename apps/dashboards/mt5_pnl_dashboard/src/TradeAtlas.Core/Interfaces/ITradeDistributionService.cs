namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface ITradeDistributionService
{
    Task DistributeTradeAsync(Trade trade, string accountId, CancellationToken ct = default);
}
