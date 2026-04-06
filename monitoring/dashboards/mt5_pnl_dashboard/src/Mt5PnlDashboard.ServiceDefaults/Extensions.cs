using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using OpenTelemetry.Trace;

namespace Mt5PnlDashboard.ServiceDefaults;

public static class Extensions
{
    public static IHostApplicationBuilder AddServiceDefaults(this IHostApplicationBuilder builder)
    {
        // Configure OpenTelemetry tracing
        builder.Services.AddOpenTelemetry()
            .WithTracing(tracing =>
            {
                tracing.AddSource("Mt5PnlDashboard");
                tracing.AddConsoleExporter();
            });

        // Add health checks
        builder.Services.AddHealthChecks();

        return builder;
    }
}
