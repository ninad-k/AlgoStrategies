using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Core.Models;

public class Account
{
    public string Id { get; set; } = string.Empty;
    public int Mt5Login { get; set; }
    public string Server { get; set; } = string.Empty;
    public string PrimaryTraderName { get; set; } = string.Empty;
    public AccountType AccountType { get; set; }
    public int Status { get; set; }
    public string? StrategiesCsv { get; set; }
    public double Balance { get; set; }
    public double Equity { get; set; }
    public string Currency { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }
    public DateTime? LastSyncAt { get; set; }

    // Navigation
    public ICollection<Trade> Trades { get; set; } = new List<Trade>();
    public ICollection<AccountTraderAssignment> TraderAssignments { get; set; } = new List<AccountTraderAssignment>();
}
