using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Mt5PnlDashboard.Core.Interfaces;
using Mt5PnlDashboard.Core.Models;

namespace Mt5PnlDashboard.ViewModels;

public partial class DashboardViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IMetricsCalculator _metricsCalculator;

    [ObservableProperty]
    private double _totalPnl;

    [ObservableProperty]
    private double _winRate;

    [ObservableProperty]
    private double _profitFactor;

    [ObservableProperty]
    private double _maxDrawdown;

    [ObservableProperty]
    private int _selectedTabIndex;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Trade> Trades { get; } = new();

    public DashboardViewModel(IUnitOfWork unitOfWork, IMetricsCalculator metricsCalculator)
    {
        _unitOfWork = unitOfWork;
        _metricsCalculator = metricsCalculator;
    }

    [RelayCommand]
    private async Task LoadDataAsync()
    {
        try
        {
            IsLoading = true;
            var trades = await _unitOfWork.Trades.GetByDateRangeAsync(DateTime.MinValue, DateTime.MaxValue);
            var tradeList = trades.ToList();

            Trades.Clear();
            foreach (var trade in tradeList)
                Trades.Add(trade);

            if (tradeList.Count > 0)
            {
                var metrics = await _metricsCalculator.CalculateAsync(tradeList);
                TotalPnl = metrics.TotalPnl;
                WinRate = metrics.WinRate;
                ProfitFactor = metrics.ProfitFactor;
                MaxDrawdown = metrics.MaxDrawdownPercent;
            }
        }
        finally
        {
            IsLoading = false;
        }
    }
}
