namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface IRuleEngine
{
    Task EvaluateTradeAsync(Trade trade, CancellationToken ct = default);
    Task<int> GetPreviewMatchCountAsync(CategorizationRule rule, CancellationToken ct = default);
}
