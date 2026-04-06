using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.Core.Models;

public class AlertNotification
{
    public int Id { get; set; }
    public string AlertType { get; set; } = string.Empty;
    public AlertSeverity Severity { get; set; }
    public string Message { get; set; } = string.Empty;
    public string? AccountId { get; set; }
    public string? StrategyName { get; set; }
    public DateTime TriggeredAt { get; set; }
    public DateTime? AcknowledgedAt { get; set; }
    public bool EmailSent { get; set; }
}
