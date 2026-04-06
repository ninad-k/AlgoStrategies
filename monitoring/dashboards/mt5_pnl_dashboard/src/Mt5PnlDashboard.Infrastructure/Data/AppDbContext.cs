using Microsoft.EntityFrameworkCore;
using Mt5PnlDashboard.Core.Models;

namespace Mt5PnlDashboard.Infrastructure.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<Trade> Trades => Set<Trade>();
    public DbSet<Strategy> Strategies => Set<Strategy>();
    public DbSet<Trader> Traders => Set<Trader>();
    public DbSet<AccountTraderAssignment> AccountTraderAssignments => Set<AccountTraderAssignment>();
    public DbSet<CategorizationRule> CategorizationRules => Set<CategorizationRule>();
    public DbSet<TradeDistributionRule> TradeDistributionRules => Set<TradeDistributionRule>();
    public DbSet<EquitySnapshot> EquitySnapshots => Set<EquitySnapshot>();
    public DbSet<AlertNotification> AlertHistory => Set<AlertNotification>();
    public DbSet<PeriodSummary> PeriodSummaries => Set<PeriodSummary>();
    public DbSet<StrategyDailyStats> StrategyDailyStats => Set<StrategyDailyStats>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // ── Trade ──────────────────────────────────────────────
        modelBuilder.Entity<Trade>(e =>
        {
            e.HasIndex(t => t.AccountId);
            e.HasIndex(t => t.Symbol);
            e.HasIndex(t => t.MagicNumber);
            e.HasIndex(t => t.StrategyName);
            e.HasIndex(t => t.TraderId);
            e.HasIndex(t => t.CategorizationStatus);
            e.HasIndex(t => t.TradeOrigin);

            e.HasIndex(t => new { t.AccountLogin, t.Ticket, t.DealExitTicket })
                .IsUnique();

            e.HasOne(t => t.Account)
                .WithMany(a => a.Trades)
                .HasForeignKey(t => t.AccountId)
                .OnDelete(DeleteBehavior.Cascade);

            e.HasOne(t => t.Trader)
                .WithMany(tr => tr.Trades)
                .HasForeignKey(t => t.TraderId)
                .OnDelete(DeleteBehavior.SetNull);
        });

        // ── AccountTraderAssignment ────────────────────────────
        modelBuilder.Entity<AccountTraderAssignment>(e =>
        {
            e.HasIndex(a => new { a.AccountId, a.TraderId })
                .IsUnique();

            e.HasOne(a => a.Account)
                .WithMany(acc => acc.TraderAssignments)
                .HasForeignKey(a => a.AccountId)
                .OnDelete(DeleteBehavior.Cascade);

            e.HasOne(a => a.Trader)
                .WithMany(tr => tr.AccountAssignments)
                .HasForeignKey(a => a.TraderId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ── EquitySnapshot ─────────────────────────────────────
        modelBuilder.Entity<EquitySnapshot>(e =>
        {
            e.HasIndex(s => new { s.AccountId, s.SnapshotDate })
                .IsUnique();
        });

        // ── CategorizationRule ─────────────────────────────────
        modelBuilder.Entity<CategorizationRule>(e =>
        {
            e.HasIndex(r => new { r.Priority, r.IsActive });

            e.HasOne(r => r.Strategy)
                .WithMany()
                .HasForeignKey(r => r.StrategyId)
                .OnDelete(DeleteBehavior.SetNull);

            e.HasOne(r => r.Trader)
                .WithMany()
                .HasForeignKey(r => r.TraderId)
                .OnDelete(DeleteBehavior.SetNull);
        });

        // ── TradeDistributionRule ──────────────────────────────
        modelBuilder.Entity<TradeDistributionRule>(e =>
        {
            e.HasIndex(r => new { r.AccountId, r.Priority });

            e.HasOne(r => r.Account)
                .WithMany()
                .HasForeignKey(r => r.AccountId)
                .OnDelete(DeleteBehavior.Cascade);

            e.HasOne(r => r.Trader)
                .WithMany()
                .HasForeignKey(r => r.TraderId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        // ── Strategy ───────────────────────────────────────────
        modelBuilder.Entity<Strategy>(e =>
        {
            e.HasIndex(s => s.Name);
        });

        // ── Trader ─────────────────────────────────────────────
        modelBuilder.Entity<Trader>(e =>
        {
            e.HasIndex(t => t.Name);
        });

        // ── StrategyDailyStats ─────────────────────────────────
        modelBuilder.Entity<StrategyDailyStats>(e =>
        {
            e.HasIndex(s => new { s.StatDate, s.AccountId });

            e.HasIndex(s => new { s.AccountId, s.StrategyName, s.StatDate })
                .IsUnique();

            e.HasOne(s => s.Account)
                .WithMany()
                .HasForeignKey(s => s.AccountId)
                .OnDelete(DeleteBehavior.Cascade);
        });
    }
}
