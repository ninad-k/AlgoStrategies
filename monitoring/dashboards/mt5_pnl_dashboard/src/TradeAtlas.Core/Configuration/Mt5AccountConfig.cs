namespace TradeAtlas.Core.Configuration;

public class Mt5AccountConfig
{
    public int Login { get; set; }
    public string Server { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string Trader { get; set; } = string.Empty;
}
