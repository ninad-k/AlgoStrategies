using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace Mt5PnlDashboard.Bridge.HealthChecks;

public class Mt5ConnectionHealthCheck : IHealthCheck
{
    public Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        return Task.FromResult(HealthCheckResult.Healthy("MT5 Bridge is running"));
    }
}
