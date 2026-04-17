using TradeAtlas.Bridge.GrpcServices;
using TradeAtlas.Bridge.HealthChecks;
using TradeAtlas.Bridge.Hubs;

var builder = WebApplication.CreateBuilder(args);

// Add gRPC services
builder.Services.AddGrpc();

// Add SignalR
builder.Services.AddSignalR();

// Add health checks
builder.Services.AddHealthChecks()
    .AddCheck<Mt5ConnectionHealthCheck>("mt5_connection");

// Configure Kestrel for HTTP/2 (gRPC) and HTTP/1.1 (SignalR)
builder.WebHost.ConfigureKestrel(options =>
{
    // HTTP/2 endpoint for gRPC
    options.ListenLocalhost(5100, listenOptions =>
    {
        listenOptions.Protocols = Microsoft.AspNetCore.Server.Kestrel.Core.HttpProtocols.Http2;
    });

    // HTTP/1.1 + HTTP/2 endpoint for SignalR and health checks
    options.ListenLocalhost(5101, listenOptions =>
    {
        listenOptions.Protocols = Microsoft.AspNetCore.Server.Kestrel.Core.HttpProtocols.Http1AndHttp2;
    });
});

var app = builder.Build();

// Map gRPC service
app.MapGrpcService<Mt5DataGrpcService>();

// Map SignalR hub
app.MapHub<LiveTradeHub>("/hubs/live-trades");

// Map health checks
app.MapHealthChecks("/health");

app.Run();
