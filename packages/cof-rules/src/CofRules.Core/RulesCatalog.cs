using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace CofRules.Core;

public sealed class SearchHit
{
    public int Id { get; set; }
    public string Kind { get; set; } = "";
    public string Name { get; set; } = "";
    public int PageStart { get; set; }
    public int PageEnd { get; set; }
    public string Snippet { get; set; } = "";
}

public sealed class RulesCatalog
{
    private readonly CofRulesDbContext _db;

    public RulesCatalog(CofRulesDbContext db)
    {
        _db = db;
    }

    public Book? GetBook() => _db.Books.AsNoTracking().OrderBy(b => b.Id).FirstOrDefault();

    public IReadOnlyList<OutlineEntry> ListOutline() =>
        _db.OutlineEntries.AsNoTracking().OrderBy(o => o.SortOrder).ToList();

    public object Stats()
    {
        var book = GetBook();
        var byKind = _db.GameElements.AsNoTracking()
            .GroupBy(e => e.Kind)
            .Select(g => new { kind = g.Key, count = g.Count() })
            .OrderBy(x => x.kind)
            .ToList();
        return new
        {
            book = book == null ? null : new { book.Title, book.Edition, book.PageCount, book.ImportedAt },
            sections = _db.Sections.Count(),
            elements = _db.GameElements.Count(),
            outline = _db.OutlineEntries.Count(),
            by_kind = byKind,
        };
    }

    public IReadOnlyList<GameElement> ListElements(string? kind = null, string? query = null, int limit = 50)
    {
        limit = Math.Clamp(limit, 1, 200);
        IQueryable<GameElement> rows = _db.GameElements.AsNoTracking().Include(e => e.Tags);
        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            rows = rows.Where(e => e.Kind == k);
        }

        if (!string.IsNullOrWhiteSpace(query))
        {
            var q = query.Trim();
            rows = rows.Where(e => e.Name.Contains(q) || (e.Summary != null && e.Summary.Contains(q)) || e.Slug.Contains(q));
        }

        return rows.OrderBy(e => e.Name).Take(limit).ToList();
    }

    public GameElement? GetElement(string nameOrSlug, string? kind = null)
    {
        var key = nameOrSlug.Trim();
        IQueryable<GameElement> rows = _db.GameElements
            .Include(e => e.Tags)
            .Include(e => e.Children)
            .Include(e => e.Outgoing)
            .Include(e => e.Parent);
        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            rows = rows.Where(e => e.Kind == k);
        }

        return rows.FirstOrDefault(e => e.Slug == key)
               ?? rows.FirstOrDefault(e => e.Name.ToLower() == key.ToLower())
               ?? rows.FirstOrDefault(e => e.Name.ToLower().Contains(key.ToLower()));
    }

    public IReadOnlyList<SearchHit> Search(string query, int limit = 20)
    {
        limit = Math.Clamp(limit, 1, 50);
        if (string.IsNullOrWhiteSpace(query))
        {
            return [];
        }

        var fts = ToFtsQuery(query);
        var sql = """
            SELECT ge.Id AS Id, ge.Kind AS Kind, ge.Name AS Name, ge.PageStart AS PageStart, ge.PageEnd AS PageEnd,
                   snippet(search_index, 4, '[', ']', '…', 18) AS Snippet
            FROM search_index
            JOIN game_elements ge ON ge.Id = search_index.element_id
            WHERE search_index MATCH $q
            LIMIT $limit
            """;
        return _db.Database.SqlQueryRaw<SearchHit>(sql,
                new SqliteParameter("$q", fts),
                new SqliteParameter("$limit", limit))
            .ToList();
    }

    public Section? GetSection(string title)
    {
        var key = title.Trim().ToLowerInvariant();
        return _db.Sections.AsNoTracking()
            .FirstOrDefault(s => s.Title.ToLower() == key)
            ?? _db.Sections.AsNoTracking().FirstOrDefault(s => s.Title.ToLower().Contains(key));
    }

    public IReadOnlyList<Section> ListSections(int? page = null, string? batchId = null)
    {
        IQueryable<Section> rows = _db.Sections.AsNoTracking();
        if (page is > 0)
        {
            rows = rows.Where(s => s.PageStart <= page && s.PageEnd >= page);
        }

        if (!string.IsNullOrWhiteSpace(batchId))
        {
            rows = rows.Where(s => s.BatchId == batchId);
        }

        return rows.OrderBy(s => s.PageStart).ThenBy(s => s.Title).ToList();
    }

    private static string ToFtsQuery(string query)
    {
        var tokens = query.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(t => t.Replace("\"", "").Replace("*", ""))
            .Where(t => t.Length > 0)
            .Select(t => t + "*");
        return string.Join(" AND ", tokens);
    }
}
