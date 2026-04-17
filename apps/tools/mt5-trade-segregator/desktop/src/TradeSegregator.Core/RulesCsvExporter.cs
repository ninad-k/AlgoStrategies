using System.Globalization;
using System.Text;
using System.Text.Json;
using TradeSegregator.Core.Models;

namespace TradeSegregator.Core;

/// <summary>Flattens <see cref="RulesDocument"/> into the CSV format consumed by the MT5 EA.</summary>
public static class RulesCsvExporter
{
    public static void WriteCsv(string path, RulesDocument rules)
    {
        ArgumentNullException.ThrowIfNull(rules);
        var sb = new StringBuilder();
        sb.AppendLine("category_id,category_label,match,field,op,value,value2,min,max");

        foreach (var cat in rules.Categories)
        {
            var match = cat.Match.Equals("any", StringComparison.OrdinalIgnoreCase) ? "any" : "all";
            foreach (var c in cat.Conditions)
            {
                var op = c.Op.ToLowerInvariant();
                string v = "", v2 = "", mn = "", mx = "";

                if (op == "between")
                {
                    mn = ElementToCsvNumber(c.Min);
                    mx = ElementToCsvNumber(c.Max);
                }
                else if (op == "contains")
                {
                    v = ElementToCsvString(c.Value);
                }
                else
                {
                    v = ElementToCsvNumber(c.Value);
                }

                sb.Append(Escape(cat.Id)).Append(',');
                sb.Append(Escape(cat.Label)).Append(',');
                sb.Append(match).Append(',');
                sb.Append(Escape(c.Field)).Append(',');
                sb.Append(Escape(op)).Append(',');
                sb.Append(Escape(v)).Append(',');
                sb.Append(Escape(v2)).Append(',');
                sb.Append(Escape(mn)).Append(',');
                sb.AppendLine(Escape(mx));
            }
        }

        File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
    }

    private static string ElementToCsvNumber(System.Text.Json.JsonElement el)
    {
        if (el.ValueKind == JsonValueKind.Undefined || el.ValueKind == JsonValueKind.Null)
            return "";
        return el.ValueKind == JsonValueKind.String
            ? el.GetString() ?? ""
            : el.GetDouble().ToString(CultureInfo.InvariantCulture);
    }

    private static string ElementToCsvString(System.Text.Json.JsonElement el)
    {
        if (el.ValueKind == JsonValueKind.Undefined || el.ValueKind == JsonValueKind.Null)
            return "";
        return el.ValueKind == JsonValueKind.String
            ? el.GetString() ?? ""
            : el.ToString();
    }

    private static string Escape(string s)
    {
        if (s.Contains('"') || s.Contains(',') || s.Contains('\n'))
            return "\"" + s.Replace("\"", "\"\"") + "\"";
        return s;
    }
}
