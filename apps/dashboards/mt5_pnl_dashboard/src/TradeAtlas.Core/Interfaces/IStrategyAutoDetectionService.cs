namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface IStrategyAutoDetectionService
{
    Task<IReadOnlyList<Strategy>> DetectStrategiesAsync(CancellationToken ct = default);
}
