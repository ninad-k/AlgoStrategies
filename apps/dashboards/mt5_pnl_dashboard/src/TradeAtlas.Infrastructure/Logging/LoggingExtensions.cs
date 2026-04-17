using System.Diagnostics;
using Microsoft.Extensions.Logging;

namespace TradeAtlas.Infrastructure.Logging;

public static class LoggingExtensions
{
    public static IDisposable? TimeOperation(this ILogger logger, string operationName, params object?[] args)
    {
        return new TimedOperation(logger, operationName, args);
    }

    private sealed class TimedOperation : IDisposable
    {
        private readonly ILogger _logger;
        private readonly string _operationName;
        private readonly object?[] _args;
        private readonly Stopwatch _stopwatch;

        public TimedOperation(ILogger logger, string operationName, object?[] args)
        {
            _logger = logger;
            _operationName = operationName;
            _args = args;
            _stopwatch = Stopwatch.StartNew();

            _logger.LogDebug("Starting operation {Operation} " + FormatArgs(), PrependOperation(args));
        }

        public void Dispose()
        {
            _stopwatch.Stop();
            _logger.LogInformation(
                "Completed operation {Operation} in {ElapsedMs}ms " + FormatArgs(),
                PrependOperationAndElapsed(_args));
        }

        private string FormatArgs()
        {
            return _args.Length > 0
                ? string.Join(" ", Enumerable.Range(0, _args.Length).Select(i => $"{{{$"Arg{i}"}}}"))
                : string.Empty;
        }

        private object?[] PrependOperation(object?[] args)
        {
            var result = new object?[args.Length + 1];
            result[0] = _operationName;
            Array.Copy(args, 0, result, 1, args.Length);
            return result;
        }

        private object?[] PrependOperationAndElapsed(object?[] args)
        {
            var result = new object?[args.Length + 2];
            result[0] = _operationName;
            result[1] = _stopwatch.ElapsedMilliseconds;
            Array.Copy(args, 0, result, 2, args.Length);
            return result;
        }
    }
}
