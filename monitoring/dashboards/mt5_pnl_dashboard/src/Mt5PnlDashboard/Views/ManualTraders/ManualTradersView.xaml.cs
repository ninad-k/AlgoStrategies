using System.Windows;
using System.Windows.Controls;
using Mt5PnlDashboard.ViewModels;

namespace Mt5PnlDashboard.Views.ManualTraders;

public partial class ManualTradersView : UserControl
{
    public ManualTradersView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is ManualTradersViewModel vm)
            vm.LoadTradersCommand.Execute(null);
    }
}
