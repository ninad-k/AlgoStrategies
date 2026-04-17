namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface IRuleEngine
{
    Task EvaluateTradeAsync(Trade trade, CancellationToken ct = default);
    Task<int> GetPreviewMatchCountAsync(CategorizationRule rule, CancellationToken ct = default);
}
