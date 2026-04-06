namespace Mt5PnlDashboard.Core.Models;

public class Trader
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? DisplayName { get; set; }
    public string? Email { get; set; }
    public bool IsActive { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation
    public ICollection<AccountTraderAssignment> AccountAssignments { get; set; } = new List<AccountTraderAssignment>();
    public ICollection<Trade> Trades { get; set; } = new List<Trade>();
}
