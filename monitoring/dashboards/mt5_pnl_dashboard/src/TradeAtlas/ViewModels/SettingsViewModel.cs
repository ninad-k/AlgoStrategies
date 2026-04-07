using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradeAtlas.Core.Interfaces;

namespace TradeAtlas.ViewModels;

public partial class SettingsViewModel : ObservableObject
{
    private readonly IDialogService _dialogService;

    [ObservableProperty]
    private string _databasePath = "tradeatlas.db";

    [ObservableProperty]
    private string _themeName = "Light";

    [ObservableProperty]
    private string _smtpHost = string.Empty;

    [ObservableProperty]
    private int _smtpPort = 587;

    public SettingsViewModel(IDialogService dialogService)
    {
        _dialogService = dialogService;
    }

    [RelayCommand]
    private async Task SaveSettingsAsync()
    {
        if (!await _dialogService.ConfirmAsync("Save all settings changes?", "Save Settings"))
            return;

        // TODO: Persist settings via ISettingsService
        await Task.CompletedTask;
    }
}
