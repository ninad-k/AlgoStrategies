namespace Mt5PnlDashboard.Core.Interfaces;

using Mt5PnlDashboard.Core.Models.Enums;

public interface IReportGenerator
{
    Task<byte[]> GenerateExcelReportAsync(
        DateTime startDate,
        DateTime endDate,
        string? accountId = null,
        TradeOrigin? originFilter = null,
        CancellationToken ct = default);
}
