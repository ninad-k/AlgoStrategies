namespace Mt5PnlDashboard.Core.Interfaces;

public interface IDialogService
{
    Task<bool?> ShowDialogAsync<TViewModel>(TViewModel viewModel) where TViewModel : class;
}
