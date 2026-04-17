using Microsoft.AspNetCore.SignalR;

namespace TradeAtlas.Bridge.Hubs;

public class LivePositionUpdate
{
    public long Ticket { get; set; }
    public string Symbol { get; set; } = string.Empty;
    public int Direction { get; set; }
    public int MagicNumber { get; set; }
    public long OpenTimeUtc { get; set; }
    public double OpenPrice { get; set; }
    public double CurrentPrice { get; set; }
    public double Volume { get; set; }
    public double UnrealizedPnl { get; set; }
    public double Commission { get; set; }
    public double Swap { get; set; }
    public double Sl { get; set; }
    public double Tp { get; set; }
    public string OrderComment { get; set; } = string.Empty;
}

public class LiveTradeHub : Hub
{
    private readonly ILogger<LiveTradeHub> _logger;

    public LiveTradeHub(ILogger<LiveTradeHub> logger)
    {
        _logger = logger;
    }

    public async Task SendPositionUpdate(LivePositionUpdate update)
    {
        _logger.LogDebug("Broadcasting position update for ticket {Ticket}", update.Ticket);
        await Clients.All.SendAsync("PositionUpdated", update);
    }

    public async Task JoinAccountGroup(string accountLogin)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, accountLogin);
        _logger.LogInformation("Client {ConnectionId} joined account group {Account}",
            Context.ConnectionId, accountLogin);
    }

    public async Task LeaveAccountGroup(string accountLogin)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, accountLogin);
        _logger.LogInformation("Client {ConnectionId} left account group {Account}",
            Context.ConnectionId, accountLogin);
    }
}
