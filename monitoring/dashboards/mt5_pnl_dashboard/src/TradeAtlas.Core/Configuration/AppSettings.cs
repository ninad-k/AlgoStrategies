namespace TradeAtlas.Core.Configuration;

public class AppSettings
{
    public DatabaseSettings Database { get; set; } = new();
    public SmtpSettings Smtp { get; set; } = new();
    public List<Mt5AccountConfig> Mt5AccountConfigs { get; set; } = new();
    public ReportScheduleSettings ReportSchedule { get; set; } = new();
    public AlertThresholds AlertThresholds { get; set; } = new();
    public string ThemeName { get; set; } = "Dark";
}
