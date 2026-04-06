using System.Windows;
using System.Windows.Controls;
using Mt5PnlDashboard.ViewModels;

namespace Mt5PnlDashboard.Views.Dashboard;

public partial class DashboardView : UserControl
{
    public DashboardView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is DashboardViewModel vm)
            vm.LoadDataCommand.Execute(null);
    }
}
