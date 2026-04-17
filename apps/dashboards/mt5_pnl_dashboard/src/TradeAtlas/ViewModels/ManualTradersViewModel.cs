using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.ViewModels;

public partial class ManualTradersViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IMetricsCalculator _metricsCalculator;
    private readonly IDialogService _dialogService;

    [ObservableProperty]
    private Trader? _selectedTrader;

    [ObservableProperty]
    private double _selectedTraderPnl;

    [ObservableProperty]
    private double _selectedTraderWinRate;

    public ObservableCollection<Trader> Traders { get; } = new();

    public ManualTradersViewModel(IUnitOfWork unitOfWork, IMetricsCalculator metricsCalculator, IDialogService dialogService)
    {
        _unitOfWork = unitOfWork;
        _metricsCalculator = metricsCalculator;
        _dialogService = dialogService;
    }

    partial void OnSelectedTraderChanged(Trader? value)
    {
        if (value != null)
            _ = LoadTraderMetricsAsync(value);
    }

    private async Task LoadTraderMetricsAsync(Trader trader)
    {
        var trades = await _unitOfWork.Trades.GetByOriginAsync(Core.Models.Enums.TradeOrigin.Manual);
        var traderTrades = trades.Where(t => t.TraderId == trader.Id).ToList();
        if (traderTrades.Count > 0)
        {
            var metrics = await _metricsCalculator.CalculateAsync(traderTrades);
            SelectedTraderPnl = metrics.TotalPnl;
            SelectedTraderWinRate = metrics.WinRate;
        }
        else
        {
            SelectedTraderPnl = 0;
            SelectedTraderWinRate = 0;
        }
    }

    [RelayCommand]
    private async Task LoadTradersAsync()
    {
        var traders = await _unitOfWork.Traders.GetAllAsync();

        Traders.Clear();
        foreach (var trader in traders)
            Traders.Add(trader);
    }

    [RelayCommand]
    private async Task AddTraderAsync()
    {
        if (!await _dialogService.ConfirmAsync("Are you sure you want to add a new trader?", "Add Trader"))
            return;

        var trader = new Trader
        {
            Id = Guid.NewGuid().ToString(),
            Name = "New Trader",
            IsActive = true,
            CreatedAt = DateTime.UtcNow
        };
        await _unitOfWork.Traders.AddAsync(trader);
        await _unitOfWork.SaveChangesAsync();
        Traders.Add(trader);
    }

    [RelayCommand]
    private async Task EditTraderAsync()
    {
        if (SelectedTrader == null) return;
        if (!await _dialogService.ConfirmAsync("Save changes to the selected trader?", "Save Trader"))
            return;

        SelectedTrader.UpdatedAt = DateTime.UtcNow;
        await _unitOfWork.SaveChangesAsync();
    }

    [RelayCommand]
    private async Task DeleteTraderAsync()
    {
        if (SelectedTrader == null) return;
        if (!await _dialogService.ConfirmAsync($"Are you sure you want to delete trader '{SelectedTrader.Name}'? This action cannot be undone.", "Delete Trader"))
            return;

        var toDelete = SelectedTrader;
        await _unitOfWork.Traders.DeleteAsync(toDelete.Id);
        await _unitOfWork.SaveChangesAsync();
        Traders.Remove(toDelete);
        SelectedTrader = null;
    }
}
