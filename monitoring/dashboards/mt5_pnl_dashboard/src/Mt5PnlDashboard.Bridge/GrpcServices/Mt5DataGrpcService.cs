using Grpc.Core;
using Mt5PnlDashboard.Bridge.Protos;

namespace Mt5PnlDashboard.Bridge.GrpcServices;

public class Mt5DataGrpcService : Mt5DataService.Mt5DataServiceBase
{
    private readonly ILogger<Mt5DataGrpcService> _logger;
    private const string NotConnectedError = "Not connected to MT5 terminal";

    public Mt5DataGrpcService(ILogger<Mt5DataGrpcService> logger)
    {
        _logger = logger;
    }

    public override Task<AccountInfoResponse> GetAccountInfo(
        AccountInfoRequest request, ServerCallContext context)
    {
        _logger.LogWarning("GetAccountInfo called but MT5 terminal is not connected");
        return Task.FromResult(new AccountInfoResponse
        {
            Success = false,
            Error = NotConnectedError
        });
    }

    public override Task<TradeHistoryResponse> GetTradeHistory(
        TradeHistoryRequest request, ServerCallContext context)
    {
        _logger.LogWarning("GetTradeHistory called but MT5 terminal is not connected");
        return Task.FromResult(new TradeHistoryResponse
        {
            Success = false,
            Error = NotConnectedError
        });
    }

    public override Task<OpenPositionsResponse> GetOpenPositions(
        OpenPositionsRequest request, ServerCallContext context)
    {
        _logger.LogWarning("GetOpenPositions called but MT5 terminal is not connected");
        return Task.FromResult(new OpenPositionsResponse
        {
            Success = false,
            Error = NotConnectedError
        });
    }

    public override Task<TestConnectionResponse> TestConnection(
        TestConnectionRequest request, ServerCallContext context)
    {
        _logger.LogWarning("TestConnection called but MT5 terminal is not connected");
        return Task.FromResult(new TestConnectionResponse
        {
            Success = false,
            Error = NotConnectedError
        });
    }
}
