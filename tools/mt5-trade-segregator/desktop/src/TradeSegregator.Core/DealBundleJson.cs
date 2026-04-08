using System.Text.Json;
using TradeSegregator.Core.Models;

namespace TradeSegregator.Core;

public static class DealBundleJson
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public static DealExportBundle ReadBundle(string path)
    {
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<DealExportBundle>(json, Options)
               ?? throw new InvalidOperationException("Empty bundle.");
    }

    public static RulesDocument ReadRules(string path)
    {
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<RulesDocument>(json, Options)
               ?? throw new InvalidOperationException("Empty rules.");
    }

    public static void WriteBundle(string path, DealExportBundle bundle)
    {
        var json = JsonSerializer.Serialize(bundle, Options);
        File.WriteAllText(path, json);
    }

    public static void WriteRules(string path, RulesDocument rules)
    {
        var json = JsonSerializer.Serialize(rules, Options);
        File.WriteAllText(path, json);
    }
}
