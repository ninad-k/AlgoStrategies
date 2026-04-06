namespace Mt5PnlDashboard.Core.Interfaces;

public interface IMt5DataService
{
    Task SyncAccountAsync(string accountId, CancellationToken ct = default);
    Task SyncAllAccountsAsync(CancellationToken ct = default);
}
