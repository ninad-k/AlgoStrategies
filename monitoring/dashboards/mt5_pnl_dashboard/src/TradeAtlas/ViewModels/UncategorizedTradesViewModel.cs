using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;
using TradeAtlas.Core.Models.Enums;

namespace TradeAtlas.ViewModels;

public partial class UncategorizedTradesViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IRuleEngine _ruleEngine;
    private readonly IDialogService _dialogService;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Trade> Trades { get; } = new();

    public UncategorizedTradesViewModel(IUnitOfWork unitOfWork, IRuleEngine ruleEngine, IDialogService dialogService)
    {
        _unitOfWork = unitOfWork;
        _ruleEngine = ruleEngine;
        _dialogService = dialogService;
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
        if (!await _dialogService.ConfirmAsync("Assign selected trades manually?", "Manual Assignment"))
            return;

        // TODO: Open dialog to manually assign selected trades to a strategy/trader
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task AssignAutoAsync()
    {
        if (!await _dialogService.ConfirmAsync("Auto-assign trades based on rule engine?", "Auto Assignment"))
            return;

        // TODO: Auto-assign based on rule engine matches
        await Task.CompletedTask;
    }

    [RelayCommand]
    private async Task AutoClassifyAsync()
    {
        if (!await _dialogService.ConfirmAsync($"Auto-classify all {Trades.Count} uncategorized trades? This will apply categorization rules to each trade.", "Auto Classify"))
            return;

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
