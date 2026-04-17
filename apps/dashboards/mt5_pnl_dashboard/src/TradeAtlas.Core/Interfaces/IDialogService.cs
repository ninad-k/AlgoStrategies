namespace TradeAtlas.Core.Interfaces;

public interface IDialogService
{
    Task<bool?> ShowDialogAsync<TViewModel>(TViewModel viewModel) where TViewModel : class;
    Task<bool> ConfirmAsync(string message, string title = "Confirm");
}
