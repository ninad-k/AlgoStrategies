using System.Windows;
using System.Windows.Controls;
using TradeAtlas.ViewModels;

namespace TradeAtlas.Views.AccountManager;

public partial class AccountManagerView : UserControl
{
    public AccountManagerView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is AccountManagerViewModel vm)
            vm.LoadAccountsCommand.Execute(null);
    }
}
