namespace TradeAtlas.Core.Interfaces;

using TradeAtlas.Core.Models;

public interface IAccountRepository
{
    Task<Account?> GetByIdAsync(string id, CancellationToken ct = default);
    Task<IReadOnlyList<Account>> GetAllAsync(CancellationToken ct = default);
    Task<Account?> GetByLoginAsync(int login, CancellationToken ct = default);
    Task AddAsync(Account account, CancellationToken ct = default);
    Task UpdateAsync(Account account, CancellationToken ct = default);
    Task<int> GetCountAsync(CancellationToken ct = default);
}
