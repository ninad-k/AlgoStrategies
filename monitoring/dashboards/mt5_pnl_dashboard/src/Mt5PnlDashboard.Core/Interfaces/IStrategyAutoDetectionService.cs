namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface IStrategyAutoDetectionService
{
    Task<IReadOnlyList<Strategy>> DetectStrategiesAsync(CancellationToken ct = default);
}
