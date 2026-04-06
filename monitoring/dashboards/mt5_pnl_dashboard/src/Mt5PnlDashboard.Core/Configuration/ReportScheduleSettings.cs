namespace Mt5PnlDashboard.Core.Configuration;

public class ReportScheduleSettings
{
    public bool Enabled { get; set; }
    public string CronExpression { get; set; } = string.Empty;
    public List<string> ReportTypes { get; set; } = new();
    public List<string> EmailRecipients { get; set; } = new();
}
