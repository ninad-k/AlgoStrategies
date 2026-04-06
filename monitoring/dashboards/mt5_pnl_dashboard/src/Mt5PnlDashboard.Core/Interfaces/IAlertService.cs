namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface IAlertService
{
    Task CheckThresholdsAsync(CancellationToken ct = default);
    Task<IReadOnlyList<AlertNotification>> GetUnacknowledgedAsync(CancellationToken ct = default);
}
