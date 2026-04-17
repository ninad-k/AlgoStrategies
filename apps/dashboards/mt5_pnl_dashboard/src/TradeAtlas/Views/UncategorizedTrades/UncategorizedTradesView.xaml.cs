using System.Windows;
using System.Windows.Controls;
using TradeAtlas.ViewModels;

namespace TradeAtlas.Views.UncategorizedTrades;

public partial class UncategorizedTradesView : UserControl
{
    public UncategorizedTradesView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is UncategorizedTradesViewModel vm)
            vm.LoadUncategorizedCommand.Execute(null);
    }
}
