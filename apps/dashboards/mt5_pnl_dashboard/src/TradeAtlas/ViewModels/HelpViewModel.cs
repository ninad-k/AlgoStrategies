using CommunityToolkit.Mvvm.ComponentModel;

namespace TradeAtlas.ViewModels;

public partial class HelpViewModel : ObservableObject
{
    [ObservableProperty]
    private string _helpContent = """
        TradeAtlas — REY CAPITAL · Smart Investments

        Navigation:
          Ctrl+D  Dashboard overview
          Ctrl+A  Account Manager
          Ctrl+S  Strategy Manager
          Ctrl+T  Manual Traders
          Ctrl+U  Uncategorized Trades
          Ctrl+L  Live Trades
          Ctrl+R  Reports
          Ctrl+,  Settings
          F1      This help screen

        Getting Started:
          1. Add an MT5 account via Account Manager.
          2. Sync historical trades.
          3. Define strategies or let auto-detection classify them.
          4. Review uncategorized trades and assign manually if needed.
          5. Monitor live positions and generate P&L reports.

        For more information, see the documentation in docs/dashboards/.
        """;
}
