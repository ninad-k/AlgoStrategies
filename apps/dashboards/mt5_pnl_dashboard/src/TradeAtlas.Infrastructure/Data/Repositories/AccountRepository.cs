using Microsoft.EntityFrameworkCore;
using TradeAtlas.Core.Interfaces;
using TradeAtlas.Core.Models;

namespace TradeAtlas.Infrastructure.Data.Repositories;

public class AccountRepository : IAccountRepository
{
    private readonly AppDbContext _context;

    public AccountRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<Account?> GetByIdAsync(string id, CancellationToken ct = default)
    {
        return await _context.Accounts.FirstOrDefaultAsync(a => a.Id == id, ct);
    }

    public async Task<IReadOnlyList<Account>> GetAllAsync(CancellationToken ct = default)
    {
        return await _context.Accounts.ToListAsync(ct);
    }

    public async Task<Account?> GetByLoginAsync(int login, CancellationToken ct = default)
    {
        return await _context.Accounts.FirstOrDefaultAsync(a => a.Mt5Login == login, ct);
    }

    public async Task AddAsync(Account account, CancellationToken ct = default)
    {
        await _context.Accounts.AddAsync(account, ct);
    }

    public Task UpdateAsync(Account account, CancellationToken ct = default)
    {
        _context.Accounts.Update(account);
        return Task.CompletedTask;
    }

    public async Task<int> GetCountAsync(CancellationToken ct = default)
    {
        return await _context.Accounts.CountAsync(ct);
    }
}
