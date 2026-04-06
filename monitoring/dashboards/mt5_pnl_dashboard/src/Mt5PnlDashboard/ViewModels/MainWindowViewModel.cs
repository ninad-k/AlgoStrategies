using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace Mt5PnlDashboard.ViewModels;

public partial class MainWindowViewModel : ObservableObject
{
    private readonly DashboardViewModel _dashboardVm;
    private readonly AccountManagerViewModel _accountManagerVm;
    private readonly StrategyManagementViewModel _strategyManagementVm;
    private readonly ManualTradersViewModel _manualTradersVm;
    private readonly UncategorizedTradesViewModel _uncategorizedTradesVm;
    private readonly LiveTradesViewModel _liveTradesVm;
    private readonly ReportsViewModel _reportsVm;
    private readonly SettingsViewModel _settingsVm;
    private readonly HelpViewModel _helpVm;

    [ObservableProperty]
    private object? _currentView;

    [ObservableProperty]
    private string _title = "MT5 P&L Dashboard";

    [ObservableProperty]
    private string _statusMessage = "Ready";

    [ObservableProperty]
    private int _uncategorizedCount;

    public MainWindowViewModel(
        DashboardViewModel dashboardVm,
        AccountManagerViewModel accountManagerVm,
        StrategyManagementViewModel strategyManagementVm,
        ManualTradersViewModel manualTradersVm,
        UncategorizedTradesViewModel uncategorizedTradesVm,
        LiveTradesViewModel liveTradesVm,
        ReportsViewModel reportsVm,
        SettingsViewModel settingsVm,
        HelpViewModel helpVm)
    {
        _dashboardVm = dashboardVm;
        _accountManagerVm = accountManagerVm;
        _strategyManagementVm = strategyManagementVm;
        _manualTradersVm = manualTradersVm;
        _uncategorizedTradesVm = uncategorizedTradesVm;
        _liveTradesVm = liveTradesVm;
        _reportsVm = reportsVm;
        _settingsVm = settingsVm;
        _helpVm = helpVm;

        CurrentView = _dashboardVm;
    }

    [RelayCommand]
    private void ShowDashboard() => CurrentView = _dashboardVm;

    [RelayCommand]
    private void ShowAccountManager() => CurrentView = _accountManagerVm;

    [RelayCommand]
    private void ShowStrategyManager() => CurrentView = _strategyManagementVm;

    [RelayCommand]
    private void ShowManualTraders() => CurrentView = _manualTradersVm;

    [RelayCommand]
    private void ShowUncategorizedTrades() => CurrentView = _uncategorizedTradesVm;

    [RelayCommand]
    private void ShowLiveTrades() => CurrentView = _liveTradesVm;

    [RelayCommand]
    private void ShowReports() => CurrentView = _reportsVm;

    [RelayCommand]
    private void ShowSettings() => CurrentView = _settingsVm;

    [RelayCommand]
    private void ShowHelp() => CurrentView = _helpVm;
}
