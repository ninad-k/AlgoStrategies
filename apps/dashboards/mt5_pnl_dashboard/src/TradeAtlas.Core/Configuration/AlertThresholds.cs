namespace TradeAtlas.Core.Configuration;

public class AlertThresholds
{
    public double MaxDrawdownPercent { get; set; } = 10.0;
    public double DailyLossLimit { get; set; } = 500.0;
    public int ConsecutiveLossCount { get; set; } = 5;
}
