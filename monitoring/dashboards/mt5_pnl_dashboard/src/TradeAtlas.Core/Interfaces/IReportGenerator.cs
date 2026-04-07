namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models.Enums;

public interface IReportGenerator
{
    Task<byte[]> GenerateExcelReportAsync(
        DateTime startDate,
        DateTime endDate,
        string? accountId = null,
        TradeOrigin? originFilter = null,
        CancellationToken ct = default);
}
