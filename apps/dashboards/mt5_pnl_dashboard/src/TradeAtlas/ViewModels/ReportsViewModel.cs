using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace TradeAtlas.ViewModels;

public partial class ReportsViewModel : ObservableObject
{
    [ObservableProperty]
    private string _selectedPeriod = "Monthly";

    [ObservableProperty]
    private DateTime _startDate = DateTime.Today.AddMonths(-1);

    [ObservableProperty]
    private DateTime _endDate = DateTime.Today;

    [ObservableProperty]
    private bool _isGenerating;

    [RelayCommand]
    private async Task GenerateReportAsync()
    {
        try
        {
            IsGenerating = true;
            // TODO: Generate report using IReportGenerator
            await Task.Delay(100); // Placeholder
        }
        finally
        {
            IsGenerating = false;
        }
    }
}
