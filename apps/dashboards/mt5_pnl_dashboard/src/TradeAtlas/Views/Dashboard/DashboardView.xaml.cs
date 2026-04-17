using System.Windows;
using System.Windows.Controls;
using TradeAtlas.ViewModels;

namespace TradeAtlas.Views.Dashboard;

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
