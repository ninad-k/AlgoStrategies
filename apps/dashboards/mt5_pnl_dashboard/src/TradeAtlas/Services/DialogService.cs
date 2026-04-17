using System.Windows;
using TradeAtlas.Core.Interfaces;

namespace TradeAtlas.Services;

public class DialogService : IDialogService
{
    public Task<bool> ConfirmAsync(string message, string title = "Confirm")
    {
        var result = MessageBox.Show(
            message,
            title,
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);

        return Task.FromResult(result == MessageBoxResult.Yes);
    }

    public Task<bool?> ShowDialogAsync<TViewModel>(TViewModel viewModel) where TViewModel : class
    {
        // Placeholder for custom dialog windows
        return Task.FromResult<bool?>(null);
    }
}
