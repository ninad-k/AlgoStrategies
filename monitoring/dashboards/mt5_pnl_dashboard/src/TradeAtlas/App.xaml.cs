using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Infrastructure.Data;
using TradeAtlas.Infrastructure.Data.Repositories;
using TradeAtlas.Infrastructure.Services;
using TradeAtlas.Infrastructure.Services.RuleMatchers;
using TradeAtlas.Services;
using TradeAtlas.ViewModels;
using Microsoft.EntityFrameworkCore;
using System.Windows;

namespace TradeAtlas;

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
                    options.UseSqlite("Data Source=tradeatlas.db"));

                // Repositories
                services.AddScoped<IUnitOfWork, UnitOfWork>();
                services.AddScoped<ITradeRepository, TradeRepository>();
                services.AddScoped<IAccountRepository, AccountRepository>();
                services.AddScoped<IStrategyRepository, StrategyRepository>();
                services.AddScoped<ITraderRepository, TraderRepository>();
                services.AddScoped<ICategorizationRuleRepository, CategorizationRuleRepository>();
                services.AddScoped<ITradeDistributionRuleRepository, TradeDistributionRuleRepository>();
                services.AddScoped<IEquitySnapshotRepository, EquitySnapshotRepository>();

                // Services
                services.AddSingleton<IDialogService, DialogService>();
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
