namespace TradeAtlas.Core.Interfaces;

public interface ISettingsService
{
    Task<T?> GetAsync<T>(string key, CancellationToken ct = default);
    Task SaveAsync<T>(string key, T value, CancellationToken ct = default);
}
