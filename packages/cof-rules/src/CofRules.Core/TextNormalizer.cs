using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace CofRules.Core;

public static partial class TextNormalizer
{
    [GeneratedRegex(@"Édouard\s+WILLISSECK[^\n]*", RegexOptions.IgnoreCase)]
    private static partial Regex WatermarkRegex();

    [GeneratedRegex(@"edouard\.willisseck@gmail\.com[^\n]*", RegexOptions.IgnoreCase)]
    private static partial Regex EmailRegex();

    [GeneratedRegex(@"^\s*(PAGE\s+\d+\s*[^\n]*|INTRO|PERSO|RÈGLES|RÈGLES)\s*$", RegexOptions.IgnoreCase | RegexOptions.Multiline)]
    private static partial Regex RunningHeaderRegex();

    [GeneratedRegex(@"(\w)[\-‑]\s*\n\s*(\w)")]
    private static partial Regex HyphenLineBreakRegex();

    public static string CleanBody(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "";
        }

        var value = WatermarkRegex().Replace(text, "");
        value = EmailRegex().Replace(value, "");
        value = RunningHeaderRegex().Replace(value, "");
        value = HyphenLineBreakRegex().Replace(value, "$1$2");
        value = value.Replace("\r\n", "\n");
        while (value.Contains("\n\n\n"))
        {
            value = value.Replace("\n\n\n", "\n\n");
        }

        return value.Trim();
    }

    public static string Slugify(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "untitled";
        }

        var normalized = value.Trim().Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(normalized.Length);
        foreach (var ch in normalized)
        {
            var category = CharUnicodeInfo.GetUnicodeCategory(ch);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(ch))
            {
                builder.Append(char.ToLowerInvariant(ch));
            }
            else if (ch is ' ' or '-' or '_' or '/' or '\'' or '’')
            {
                builder.Append('-');
            }
        }

        var slug = Regex.Replace(builder.ToString(), "-{2,}", "-").Trim('-');
        return string.IsNullOrEmpty(slug) ? "untitled" : slug;
    }

    public static string NormalizeName(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        return Regex.Replace(value.Trim(), @"\s+", " ");
    }
}
