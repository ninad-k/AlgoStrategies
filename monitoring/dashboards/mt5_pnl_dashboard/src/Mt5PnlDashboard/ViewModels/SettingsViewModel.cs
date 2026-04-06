using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace Mt5PnlDashboard.ViewModels;

public partial class SettingsViewModel : ObservableObject
{
    [ObservableProperty]
    private string _databasePath = "mt5_pnl_dashboard.db";

    [ObservableProperty]
    private string _themeName = "Light";

    [ObservableProperty]
    private string _smtpHost = string.Empty;

    [ObservableProperty]
    private int _smtpPort = 587;

    [RelayCommand]
    private async Task SaveSettingsAsync()
    {
        // TODO: Persist settings via ISettingsService
        await Task.CompletedTask;
    }
}
