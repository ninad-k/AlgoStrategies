namespace Mt5PnlDashboard.Core.Interfaces;

public interface IPnlAggregator
{
    Task AggregateDailyAsync(string accountId, DateTime date, CancellationToken ct = default);
    Task AggregateWeeklyAsync(string accountId, DateTime weekStart, CancellationToken ct = default);
    Task AggregateMonthlyAsync(string accountId, int year, int month, CancellationToken ct = default);
}
