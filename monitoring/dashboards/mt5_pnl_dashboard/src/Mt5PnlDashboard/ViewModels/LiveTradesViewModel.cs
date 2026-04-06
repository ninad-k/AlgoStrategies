using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Mt5PnlDashboard.Core.Models;

namespace Mt5PnlDashboard.ViewModels;

public partial class LiveTradesViewModel : ObservableObject
{
    [ObservableProperty]
    private bool _isConnected;

    [ObservableProperty]
    private double _totalUnrealizedPnl;

    public ObservableCollection<LivePosition> OpenPositions { get; } = new();

    [RelayCommand]
    private async Task ConnectAsync()
    {
        // TODO: Connect to MT5 via SignalR or pipe
        IsConnected = true;
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task DisconnectAsync()
    {
        IsConnected = false;
        OpenPositions.Clear();
        TotalUnrealizedPnl = 0;
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task RefreshAsync()
    {
        if (!IsConnected) return;
        // TODO: Fetch live positions from MT5 service
        TotalUnrealizedPnl = OpenPositions.Sum(p => p.UnrealizedPnl);
        await Task.CompletedTask;
    }
}
