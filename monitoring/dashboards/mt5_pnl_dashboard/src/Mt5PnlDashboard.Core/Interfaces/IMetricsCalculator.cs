namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Metrics;
using Mt5PnlDashboard.Core.Models;

public interface IMetricsCalculator
{
    Task<MetricsResult> CalculateAsync(IEnumerable<Trade> trades, CancellationToken ct = default);
}
