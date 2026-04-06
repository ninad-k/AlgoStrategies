using System.Windows;
using System.Windows.Controls;
using Mt5PnlDashboard.ViewModels;

namespace Mt5PnlDashboard.Views.StrategyManager;

public partial class StrategyManagementView : UserControl
{
    public StrategyManagementView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is StrategyManagementViewModel vm)
            vm.LoadStrategiesCommand.Execute(null);
    }
}
