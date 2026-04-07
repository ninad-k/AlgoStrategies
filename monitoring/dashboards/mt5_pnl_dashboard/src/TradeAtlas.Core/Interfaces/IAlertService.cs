namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface IAlertService
{
    Task CheckThresholdsAsync(CancellationToken ct = default);
    Task<IReadOnlyList<AlertNotification>> GetUnacknowledgedAsync(CancellationToken ct = default);
}
