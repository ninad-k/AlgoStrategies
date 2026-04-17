using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.ViewModels;

public partial class StrategyManagementViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IDialogService _dialogService;

    [ObservableProperty]
    private Strategy? _selectedStrategy;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Strategy> Strategies { get; } = new();

    public StrategyManagementViewModel(IUnitOfWork unitOfWork, IDialogService dialogService)
    {
        _unitOfWork = unitOfWork;
        _dialogService = dialogService;
    }

    [RelayCommand]
    private async Task LoadStrategiesAsync()
    {
        try
        {
            IsLoading = true;
            var strategies = await _unitOfWork.Strategies.GetAllAsync();

            Strategies.Clear();
            foreach (var strategy in strategies)
                Strategies.Add(strategy);
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    private async Task AddStrategyAsync()
    {
        if (!await _dialogService.ConfirmAsync("Are you sure you want to add a new strategy?", "Add Strategy"))
            return;

        var strategy = new Strategy
        {
            Id = Guid.NewGuid().ToString(),
            Name = "New Strategy",
            Color = "#4CAF50",
            CreatedAt = DateTime.UtcNow
        };
        await _unitOfWork.Strategies.AddAsync(strategy);
        await _unitOfWork.SaveChangesAsync();
        Strategies.Add(strategy);
    }

    [RelayCommand]
    private async Task EditStrategyAsync()
    {
        if (SelectedStrategy == null) return;
        if (!await _dialogService.ConfirmAsync("Save changes to the selected strategy?", "Save Strategy"))
            return;

        SelectedStrategy.UpdatedAt = DateTime.UtcNow;
        await _unitOfWork.SaveChangesAsync();
    }

    [RelayCommand]
    private async Task DeleteStrategyAsync()
    {
        if (SelectedStrategy == null) return;
        if (!await _dialogService.ConfirmAsync($"Are you sure you want to delete strategy '{SelectedStrategy.Name}'? This action cannot be undone.", "Delete Strategy"))
            return;

        var toDelete = SelectedStrategy;
        await _unitOfWork.Strategies.DeleteAsync(toDelete.Id);
        await _unitOfWork.SaveChangesAsync();
        Strategies.Remove(toDelete);
        SelectedStrategy = null;
    }

    [RelayCommand]
    private async Task AutoDetectAsync()
    {
        // TODO: Implement auto-detection of strategies from trade patterns
        await LoadStrategiesAsync();
    }
}
