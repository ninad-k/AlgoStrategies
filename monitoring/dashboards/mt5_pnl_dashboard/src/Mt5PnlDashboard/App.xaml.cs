using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Mt5PnlDashboard.Core.Interfaces;
using Mt5PnlDashboard.Infrastructure.Data;
using Mt5PnlDashboard.Infrastructure.Data.Repositories;
using Mt5PnlDashboard.Infrastructure.Services;
using Mt5PnlDashboard.Infrastructure.Services.RuleMatchers;
using Mt5PnlDashboard.ViewModels;
using Microsoft.EntityFrameworkCore;
using System.Windows;

namespace Mt5PnlDashboard;

public partial class App : Application
{
    private IHost? _host;

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _host = Host.CreateDefaultBuilder()
            .ConfigureServices((context, services) =>
            {
                // Database
                services.AddDbContext<AppDbContext>(options =>
                    options.UseSqlite("Data Source=mt5_pnl_dashboard.db"));

                // Repositories
                services.AddScoped<IUnitOfWork, UnitOfWork>();

                // Services
                services.AddScoped<IMetricsCalculator, MetricsCalculator>();
                services.AddScoped<IRuleEngine, RuleEngine>();
                services.AddScoped<IRuleMatcher, MagicNumberRuleMatcher>();
                services.AddScoped<IRuleMatcher, LotSizeRuleMatcher>();
                services.AddScoped<IRuleMatcher, CommentPatternRuleMatcher>();
                services.AddScoped<IRuleMatcher, SymbolPatternRuleMatcher>();
                services.AddScoped<IRuleMatcher, TimeOfDayRuleMatcher>();

                // ViewModels
                services.AddTransient<MainWindowViewModel>();
                services.AddTransient<DashboardViewModel>();
                services.AddTransient<AccountManagerViewModel>();
                services.AddTransient<StrategyManagementViewModel>();
                services.AddTransient<ManualTradersViewModel>();
                services.AddTransient<UncategorizedTradesViewModel>();
                services.AddTransient<LiveTradesViewModel>();
                services.AddTransient<ReportsViewModel>();
                services.AddTransient<SettingsViewModel>();
                services.AddTransient<HelpViewModel>();

                // Main Window
                services.AddSingleton<MainWindow>();
            })
            .Build();

        await _host.StartAsync();

        // Ensure database created
        using var scope = _host.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        await db.Database.EnsureCreatedAsync();

        var mainWindow = _host.Services.GetRequiredService<MainWindow>();
        mainWindow.DataContext = _host.Services.GetRequiredService<MainWindowViewModel>();
        mainWindow.Show();
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        if (_host != null)
        {
            await _host.StopAsync();
            _host.Dispose();
        }
        base.OnExit(e);
    }
}
