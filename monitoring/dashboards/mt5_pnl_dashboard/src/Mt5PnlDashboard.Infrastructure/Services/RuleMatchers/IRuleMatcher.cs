using Mt5PnlDashboard.Core.Models;
using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.Infrastructure.Services.RuleMatchers;

public interface IRuleMatcher
{
    RuleType SupportedType { get; }
    bool Matches(Trade trade, CategorizationRule rule);
}
