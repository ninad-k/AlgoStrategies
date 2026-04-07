using System.Windows;
using System.Windows.Controls;
using TradeAtlas.ViewModels;

namespace TradeAtlas.Views.StrategyManager;

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
