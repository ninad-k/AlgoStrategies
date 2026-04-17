namespace TradeAtlas.Core.Models;

public class Strategy
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? Description { get; set; }
    public string? MagicNumbers { get; set; }
    public string? SymbolFilter { get; set; }
    public double? LotSizeMin { get; set; }
    public double? LotSizeMax { get; set; }
    public string? CommentPattern { get; set; }
    public string Color { get; set; } = string.Empty;
    public bool IsAutoDetected { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
}
