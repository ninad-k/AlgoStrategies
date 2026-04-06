using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Mt5PnlDashboard.Core.Interfaces;
using Mt5PnlDashboard.Core.Models;

namespace Mt5PnlDashboard.ViewModels;

public partial class AccountManagerViewModel : ObservableObject
{
    private readonly IUnitOfWork _unitOfWork;

    [ObservableProperty]
    private Account? _selectedAccount;

    [ObservableProperty]
    private bool _isLoading;

    public ObservableCollection<Account> Accounts { get; } = new();

    public AccountManagerViewModel(IUnitOfWork unitOfWork)
    {
        _unitOfWork = unitOfWork;
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
        await _unitOfWork.SaveChangesAsync();
    }

    [RelayCommand]
    private async Task DeleteAccountAsync()
    {
        if (SelectedAccount == null) return;
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
        // TODO: Implement MT5 account sync
        SelectedAccount.LastSyncAt = DateTime.UtcNow;
        await _unitOfWork.SaveChangesAsync();
    }
}
