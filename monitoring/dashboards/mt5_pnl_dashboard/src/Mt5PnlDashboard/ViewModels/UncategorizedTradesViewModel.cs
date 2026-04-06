using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Mt5PnlDashboard.Core.Interfaces;
using Mt5PnlDashboard.Core.Models;
using Mt5PnlDashboard.Core.Models.Enums;

namespace Mt5PnlDashboard.ViewModels;

public partial class UncategorizedTradesViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IRuleEngine _ruleEngine;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Trade> Trades { get; } = new();

    public UncategorizedTradesViewModel(IUnitOfWork unitOfWork, IRuleEngine ruleEngine)
    {
        _unitOfWork = unitOfWork;
        _ruleEngine = ruleEngine;
    }

    [RelayCommand]
    private async Task LoadUncategorizedAsync()
    {
        try
        {
            IsLoading = true;
            var uncategorized = await _unitOfWork.Trades.GetByStatusAsync(CategorizationStatus.Uncategorized);
            var uncategorizedList = uncategorized.ToList();

            Trades.Clear();
            foreach (var trade in uncategorizedList)
                Trades.Add(trade);
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    private async Task AssignManualAsync()
    {
        // TODO: Open dialog to manually assign selected trades to a strategy/trader
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task AssignAutoAsync()
    {
        // TODO: Auto-assign based on rule engine matches
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task AutoClassifyAsync()
    {
        try
        {
            IsLoading = true;
            foreach (var trade in Trades.ToList())
            {
                await _ruleEngine.EvaluateTradeAsync(trade);
            }
            await _unitOfWork.SaveChangesAsync();
            await LoadUncategorizedAsync();
        }
        finally
        {
            IsLoading = false;
        }
    }
}
