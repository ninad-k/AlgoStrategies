namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Metrics;
using TradeAtlas.Core.Models;

public interface IMetricsCalculator
{
    Task<MetricsResult> CalculateAsync(IEnumerable<Trade> trades, CancellationToken ct = default);
}
