namespace Mt5PnlDashboard.Core.Configuration;

public class DatabaseSettings
{
    public string Provider { get; set; } = "Sqlite";
    public Dictionary<string, string> ConnectionStrings { get; set; } = new();
}
