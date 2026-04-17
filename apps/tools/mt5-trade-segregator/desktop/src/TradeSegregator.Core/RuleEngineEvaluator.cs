using System.Text.Json;
using TradeSegregator.Core.Models;

namespace TradeSegregator.Core;

public static class RuleEngineEvaluator
{
    public static void ApplyRules(DealExportBundle bundle, RulesDocument rules)
    {
        ArgumentNullException.ThrowIfNull(bundle);
        ArgumentNullException.ThrowIfNull(rules);

        var uncat = string.IsNullOrWhiteSpace(rules.UncategorizedId)
            ? "uncategorized"
            : rules.UncategorizedId;

        bundle.UncategorizedId = uncat;

        foreach (var deal in bundle.Deals)
            ApplyToDeal(deal, rules);
    }

    public static void ApplyToDeal(DealRecord deal, RulesDocument rules)
    {
        var uncat = string.IsNullOrWhiteSpace(rules.UncategorizedId)
            ? "uncategorized"
            : rules.UncategorizedId;

        foreach (var cat in rules.Categories)
        {
            if (CategoryMatches(deal, cat))
            {
                deal.CategoryId = cat.Id;
                deal.CategoryLabel = cat.Label;
                return;
            }
        }

        deal.CategoryId = uncat;
        deal.CategoryLabel = "Uncategorized";
    }

    private static bool CategoryMatches(DealRecord deal, RuleCategory cat)
    {
        if (cat.Conditions.Count == 0)
            return false;

        var any = cat.Match.Equals("any", StringComparison.OrdinalIgnoreCase);

        if (any)
        {
            foreach (var c in cat.Conditions)
            {
                if (ConditionHolds(deal, c))
                    return true;
            }

            return false;
        }

        foreach (var c in cat.Conditions)
        {
            if (!ConditionHolds(deal, c))
                return false;
        }

        return true;
    }

    private static bool ConditionHolds(DealRecord deal, RuleCondition c)
    {
        var op = c.Op.ToLowerInvariant();

        if (op == "contains")
        {
            var needle = JsonString(c.Value);
            var field = c.Field.ToLowerInvariant();
            var hay = field switch
            {
                "symbol" => deal.Symbol ?? "",
                _ => ""
            };
            return hay.Contains(needle, StringComparison.OrdinalIgnoreCase);
        }

        if (op == "between")
        {
            if (c.Min.ValueKind == JsonValueKind.Undefined || c.Max.ValueKind == JsonValueKind.Undefined)
                return false;
            var lhs = GetNumericField(deal, c.Field);
            var min = c.Min.GetDouble();
            var max = c.Max.GetDouble();
            return lhs >= min && lhs <= max;
        }

        if (c.Value.ValueKind == JsonValueKind.Undefined)
            return false;

        var left = GetNumericField(deal, c.Field);
        var right = c.Value.ValueKind == JsonValueKind.String
            ? double.Parse(c.Value.GetString()!, System.Globalization.CultureInfo.InvariantCulture)
            : c.Value.GetDouble();

        return op switch
        {
            "eq" => Math.Abs(left - right) < 1e-9,
            "neq" => Math.Abs(left - right) >= 1e-9,
            "lt" => left < right,
            "lte" => left <= right,
            "gt" => left > right,
            "gte" => left >= right,
            _ => false
        };
    }

    private static string JsonString(JsonElement el)
    {
        return el.ValueKind switch
        {
            JsonValueKind.String => el.GetString() ?? "",
            _ => el.ToString()
        };
    }

    private static double GetNumericField(DealRecord d, string field)
    {
        return field.ToLowerInvariant() switch
        {
            "profit" => d.Profit,
            "volume" => d.Volume,
            "magic" => d.Magic,
            "duration_seconds" => d.DurationMinutes * 60.0,
            "duration_minutes" => d.DurationMinutes,
            "deal_type" => d.DealType,
            "entry" => d.Entry,
            _ => 0
        };
    }
}
