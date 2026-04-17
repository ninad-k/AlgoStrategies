using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.ViewModels;

public partial class AccountManagerViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IDialogService _dialogService;

    [ObservableProperty]
    private Account? _selectedAccount;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Account> Accounts { get; } = new();

    public AccountManagerViewModel(IUnitOfWork unitOfWork, IDialogService dialogService)
    {
        _unitOfWork = unitOfWork;
        _dialogService = dialogService;
    }

    [RelayCommand]
    private async Task LoadAccountsAsync()
    {
        try
        {
            IsLoading = true;
            var accounts = await _unitOfWork.Accounts.GetAllAsync();

            Accounts.Clear();
            foreach (var account in accounts)
                Accounts.Add(account);
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    private async Task AddAccountAsync()
    {
        if (!await _dialogService.ConfirmAsync("Are you sure you want to add a new account?", "Add Account"))
            return;

        var account = new Account
        {
            Id = Guid.NewGuid().ToString(),
            CreatedAt = DateTime.UtcNow
        };
        await _unitOfWork.Accounts.AddAsync(account);
        await _unitOfWork.SaveChangesAsync();
        Accounts.Add(account);
    }

    [RelayCommand]
    private async Task EditAccountAsync()
    {
        if (SelectedAccount == null) return;
        if (!await _dialogService.ConfirmAsync("Save changes to the selected account?", "Save Account"))
            return;

        await _unitOfWork.SaveChangesAsync();
    }

    [RelayCommand]
    private async Task DeleteAccountAsync()
    {
        if (SelectedAccount == null) return;
        if (!await _dialogService.ConfirmAsync($"Are you sure you want to delete account '{SelectedAccount.Mt5Login}'? This action cannot be undone.", "Delete Account"))
            return;

        var toDelete = SelectedAccount;
        // Account repository doesn't expose DeleteAsync; update status to mark as deleted
        toDelete.Status = -1;
        await _unitOfWork.Accounts.UpdateAsync(toDelete);
        await _unitOfWork.SaveChangesAsync();
        Accounts.Remove(toDelete);
        SelectedAccount = null;
    }

    [RelayCommand]
    private async Task SyncAccountAsync()
    {
        if (SelectedAccount == null) return;
        if (!await _dialogService.ConfirmAsync($"Sync account '{SelectedAccount.Mt5Login}' with MT5?", "Sync Account"))
            return;

        // TODO: Implement MT5 account sync
        SelectedAccount.LastSyncAt = DateTime.UtcNow;
        await _unitOfWork.SaveChangesAsync();
    }
}
