namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models;

public interface IEmailService
{
    Task SendReportAsync(byte[] reportData, string fileName, IEnumerable<string> recipients, CancellationToken ct = default);
    Task SendAlertAsync(AlertNotification alert, IEnumerable<string> recipients, CancellationToken ct = default);
}
