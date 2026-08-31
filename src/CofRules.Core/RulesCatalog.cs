using System.Text.Json;
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
    public string Source { get; set; } = "element";
}

public sealed class SearchResult
{
    public string Mode { get; set; } = "name";
    public string Query { get; set; } = "";
    public int? Page { get; set; }
    public object? Book { get; set; }
    public IReadOnlyList<SearchHit> Hits { get; set; } = [];
}

public sealed class RulesCatalog
{
    private readonly CofRulesDbContext _db;

    public RulesCatalog(CofRulesDbContext db)
    {
        _db = db;
    }

    public IReadOnlyList<Book> ListBooks() =>
        _db.Books.AsNoTracking().OrderBy(b => b.Title).ToList();

    public Book? ResolveBook(string? hint)
    {
        var books = _db.Books.AsNoTracking().ToList();
        if (books.Count == 0)
        {
            return null;
        }

        if (string.IsNullOrWhiteSpace(hint))
        {
            return books[0];
        }

        var folded = TextNormalizer.Fold(hint);
        var slug = TextNormalizer.Slugify(hint);
        foreach (var book in books)
        {
            var titleFolded = TextNormalizer.Fold(book.Title);
            if (book.Slug == slug || titleFolded == folded)
            {
                return book;
            }

            var aliases = JsonSerializer.Deserialize<string[]>(book.AliasesJson) ?? [];
            if (aliases.Any(a => a == folded || (a.Length >= 8 && folded.Contains(a))))
            {
                return book;
            }
        }

        return null;
    }

    public object Stats()
    {
        var books = ListBooks().Select(BookSummary).ToList();
        var byKind = _db.GameElements.AsNoTracking()
            .GroupBy(e => e.Kind)
            .Select(g => new { kind = g.Key, count = g.Count() })
            .OrderBy(x => x.kind)
            .ToList();
        return new
        {
            books,
            sections = _db.Sections.Count(),
            elements = _db.GameElements.Count(),
            outline = _db.OutlineEntries.Count(),
            by_kind = byKind,
        };
    }

    public IReadOnlyList<OutlineEntry> ListOutline(string? bookHint = null)
    {
        var book = ResolveBook(bookHint);
        IQueryable<OutlineEntry> rows = _db.OutlineEntries.AsNoTracking();
        if (book != null)
        {
            rows = rows.Where(o => o.BookId == book.Id);
        }

        return rows.OrderBy(o => o.SortOrder).ToList();
    }

    public IReadOnlyList<GameElement> ListElements(string? kind = null, string? query = null, int limit = 50, string? bookHint = null)
    {
        limit = Math.Clamp(limit, 1, 200);
        IQueryable<GameElement> rows = _db.GameElements.AsNoTracking().Include(e => e.Tags).Include(e => e.Book);
        var book = string.IsNullOrWhiteSpace(bookHint) ? null : ResolveBook(bookHint);
        if (book != null)
        {
            rows = rows.Where(e => e.BookId == book.Id);
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            rows = rows.Where(e => e.Kind == k);
        }

        if (!string.IsNullOrWhiteSpace(query))
        {
            var folded = TextNormalizer.Fold(query);
            rows = rows.Where(e => e.NameNormalized.Contains(folded) || e.Slug.Contains(query) || (e.Summary != null && e.Summary.Contains(query)));
        }

        return rows.OrderBy(e => e.Name).Take(limit).ToList();
    }

    public GameElement? GetElement(string nameOrSlug, string? kind = null, string? bookHint = null)
    {
        var key = nameOrSlug.Trim();
        var folded = TextNormalizer.Fold(key);
        IQueryable<GameElement> rows = _db.GameElements
            .Include(e => e.Tags)
            .Include(e => e.Children)
            .Include(e => e.Outgoing)
            .Include(e => e.Parent)
            .Include(e => e.Book);
        var book = string.IsNullOrWhiteSpace(bookHint) ? null : ResolveBook(bookHint);
        if (book != null)
        {
            rows = rows.Where(e => e.BookId == book.Id);
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            rows = rows.Where(e => e.Kind == k);
        }

        return rows.FirstOrDefault(e => e.Slug == key)
               ?? rows.FirstOrDefault(e => e.NameNormalized == folded)
               ?? rows.FirstOrDefault(e => e.NameNormalized.Contains(folded));
    }

    public SearchResult Search(string? query, int limit = 20, string? book = null, int? page = null, string? kind = null)
    {
        limit = Math.Clamp(limit, 1, 50);
        var parsed = QueryParser.Parse(query, book, page);
        var resolved = ResolveBook(parsed.BookHint ?? book);
        var result = new SearchResult
        {
            Query = parsed.Raw,
            Page = parsed.Page,
            Book = resolved == null ? null : BookSummary(resolved),
        };

        if (parsed.IsPageLookup)
        {
            result.Mode = "page";
            result.Hits = LookupPage(resolved, parsed.Page!.Value, kind, limit);
            return result;
        }

        result.Mode = "name";
        var name = string.IsNullOrWhiteSpace(parsed.NameQuery) ? parsed.Raw : parsed.NameQuery;
        result.Hits = SearchByName(resolved, name, kind, limit);
        return result;
    }

    public Section? GetSection(string title, string? bookHint = null)
    {
        var folded = TextNormalizer.Fold(title);
        IQueryable<Section> rows = _db.Sections.AsNoTracking().Include(s => s.Book);
        var book = string.IsNullOrWhiteSpace(bookHint) ? null : ResolveBook(bookHint);
        if (book != null)
        {
            rows = rows.Where(s => s.BookId == book.Id);
        }

        return rows.FirstOrDefault(s => s.TitleNormalized == folded)
               ?? rows.FirstOrDefault(s => s.TitleNormalized.Contains(folded));
    }

    public IReadOnlyList<Section> ListSections(int? page = null, string? batchId = null, string? bookHint = null)
    {
        IQueryable<Section> rows = _db.Sections.AsNoTracking().Include(s => s.Book);
        var book = string.IsNullOrWhiteSpace(bookHint) ? null : ResolveBook(bookHint);
        if (book != null)
        {
            rows = rows.Where(s => s.BookId == book.Id);
        }

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

    private IReadOnlyList<SearchHit> LookupPage(Book? book, int page, string? kind, int limit)
    {
        var hits = new List<SearchHit>();
        IQueryable<GameElement> elements = _db.GameElements.AsNoTracking();
        IQueryable<Section> sections = _db.Sections.AsNoTracking();
        if (book != null)
        {
            elements = elements.Where(e => e.BookId == book.Id);
            sections = sections.Where(s => s.BookId == book.Id);
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            elements = elements.Where(e => e.Kind == k);
        }

        hits.AddRange(elements
            .Where(e => e.PageStart <= page && e.PageEnd >= page)
            .OrderBy(e => e.Kind)
            .ThenBy(e => e.Name)
            .Take(limit)
            .Select(e => new SearchHit
            {
                Id = e.Id,
                Kind = e.Kind,
                Name = e.Name,
                PageStart = e.PageStart,
                PageEnd = e.PageEnd,
                Snippet = e.Summary ?? "",
                Source = "element",
            }));

        if (hits.Count < limit && string.IsNullOrWhiteSpace(kind))
        {
            hits.AddRange(sections
                .Where(s => s.PageStart <= page && s.PageEnd >= page)
                .OrderBy(s => s.PageStart)
                .Take(limit - hits.Count)
                .Select(s => new SearchHit
                {
                    Id = s.Id,
                    Kind = s.Kind,
                    Name = s.Title,
                    PageStart = s.PageStart,
                    PageEnd = s.PageEnd,
                    Snippet = s.Summary ?? "",
                    Source = "section",
                }));
        }

        return hits;
    }

    private IReadOnlyList<SearchHit> SearchByName(Book? book, string query, string? kind, int limit)
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            return [];
        }

        var folded = TextNormalizer.Fold(query);
        IQueryable<GameElement> rows = _db.GameElements.AsNoTracking();
        if (book != null)
        {
            rows = rows.Where(e => e.BookId == book.Id);
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            var k = kind.Trim().ToLowerInvariant();
            rows = rows.Where(e => e.Kind == k);
        }

        var nameHits = rows
            .Where(e => e.NameNormalized == folded || e.NameNormalized.Contains(folded))
            .AsEnumerable()
            .OrderBy(e => e.NameNormalized == folded ? 0 : 1)
            .ThenBy(e => e.NameNormalized.Length)
            .ThenBy(e => e.Name)
            .Take(limit)
            .Select(e => new SearchHit
            {
                Id = e.Id,
                Kind = e.Kind,
                Name = e.Name,
                PageStart = e.PageStart,
                PageEnd = e.PageEnd,
                Snippet = e.Summary ?? "",
                Source = "element",
            })
            .ToList();

        if (nameHits.Count >= limit)
        {
            return nameHits;
        }

        var seen = nameHits.Select(h => h.Id).ToHashSet();
        var fts = ToFtsQuery(query);
        var sql = """
            SELECT ge.Id AS Id, ge.Kind AS Kind, ge.Name AS Name, ge.PageStart AS PageStart, ge.PageEnd AS PageEnd,
                   snippet(search_index, 4, '[', ']', '…', 18) AS Snippet, 'element' AS Source
            FROM search_index
            JOIN game_elements ge ON ge.Id = search_index.element_id
            WHERE search_index MATCH $q
            """;
        if (book != null)
        {
            sql += " AND ge.BookId = $book";
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            sql += " AND ge.Kind = $kind";
        }

        sql += " LIMIT $limit";

        var parameters = new List<object>
        {
            new SqliteParameter("$q", fts),
            new SqliteParameter("$limit", limit),
        };
        if (book != null)
        {
            parameters.Add(new SqliteParameter("$book", book.Id));
        }

        if (!string.IsNullOrWhiteSpace(kind))
        {
            parameters.Add(new SqliteParameter("$kind", kind.Trim().ToLowerInvariant()));
        }

        foreach (var hit in _db.Database.SqlQueryRaw<SearchHit>(sql, parameters.ToArray()).ToList())
        {
            if (seen.Add(hit.Id))
            {
                nameHits.Add(hit);
            }

            if (nameHits.Count >= limit)
            {
                break;
            }
        }

        return nameHits;
    }

    private static object BookSummary(Book book) => new
    {
        book.Id,
        book.Slug,
        book.Title,
        book.Edition,
        page_count = book.PageCount,
    };

    private static string ToFtsQuery(string query)
    {
        var tokens = TextNormalizer.Fold(query)
            .Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(t => t.Length > 0)
            .Select(t => t + "*");
        return string.Join(" AND ", tokens);
    }
}
