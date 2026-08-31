using System.Text.RegularExpressions;

namespace CofRules.Core;

public sealed class ParsedQuery
{
    public string Raw { get; init; } = "";
    public string? BookHint { get; init; }
    public int? Page { get; init; }
    public string NameQuery { get; init; } = "";
    public bool IsPageLookup => Page is > 0;
}

public static partial class QueryParser
{
    [GeneratedRegex(
        @"(?ix)(?:(?:page|p\.?)\s*(?<page>\d+)|(?<page>\d+)\s*(?:eme|e|è|èeme)?\s*page)",
        RegexOptions.CultureInvariant)]
    private static partial Regex PageRegex();

    public static ParsedQuery Parse(string? query, string? book = null, int? page = null)
    {
        var raw = query?.Trim() ?? "";
        var remaining = raw;
        int? parsedPage = page is > 0 ? page : null;

        if (parsedPage is null && remaining.Length > 0)
        {
            var match = PageRegex().Match(remaining);
            if (match.Success && int.TryParse(match.Groups["page"].Value, out var n) && n > 0)
            {
                parsedPage = n;
                remaining = (remaining[..match.Index] + remaining[(match.Index + match.Length)..]).Trim();
            }
        }

        remaining = Regex.Replace(remaining, @"\s+", " ").Trim(' ', ',', '-', ':');

        var bookHint = string.IsNullOrWhiteSpace(book) ? remaining : book.Trim();
        var nameQuery = remaining;

        if (parsedPage is > 0)
        {
            nameQuery = "";
        }

        return new ParsedQuery
        {
            Raw = raw,
            BookHint = string.IsNullOrWhiteSpace(bookHint) ? null : bookHint,
            NameQuery = nameQuery,
            Page = parsedPage,
        };
    }
}
