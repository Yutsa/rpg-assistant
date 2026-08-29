using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace CofRules.Core;

public sealed class ImportReport
{
    public int Sections { get; set; }
    public int Elements { get; set; }
    public int Tags { get; set; }
    public int CrossRefs { get; set; }
    public int OutlineEntries { get; set; }
    public string DatabasePath { get; set; } = "";
    public List<string> Warnings { get; set; } = [];
}

public sealed class RulesImporter
{
    private readonly CofRulesDbContext _db;

    public RulesImporter(CofRulesDbContext db)
    {
        _db = db;
    }

    public ImportReport Import(
        IEnumerable<ExtractionBatch> batches,
        IReadOnlyList<TocEntry> toc,
        BookMeta meta)
    {
        _db.Database.ExecuteSqlRaw("PRAGMA foreign_keys = OFF;");
        _db.Database.ExecuteSqlRaw("DELETE FROM cross_refs;");
        _db.Database.ExecuteSqlRaw("DELETE FROM game_element_tags;");
        _db.Database.ExecuteSqlRaw("DELETE FROM game_elements;");
        _db.Database.ExecuteSqlRaw("DELETE FROM sections;");
        _db.Database.ExecuteSqlRaw("DELETE FROM outline_entries;");
        _db.Database.ExecuteSqlRaw("DELETE FROM books;");
        _db.Database.ExecuteSqlRaw("PRAGMA foreign_keys = ON;");
        _db.ChangeTracker.Clear();

        var book = new Book
        {
            Title = meta.Title,
            Edition = meta.Edition,
            PageCount = meta.PageCount,
            SourcePath = meta.SourcePath,
            ImportedAt = DateTimeOffset.UtcNow,
        };
        _db.Books.Add(book);
        _db.SaveChanges();

        var report = new ImportReport();
        ImportOutline(book, toc, report);

        var pendingParents = new List<(GameElement Element, string ParentKind, string ParentName)>();
        var pendingRefs = new List<(GameElement From, ExtractedSeeAlso Link)>();
        var usedSlugs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var batch in batches)
        {
            foreach (var section in batch.Sections)
            {
                _db.Sections.Add(new Section
                {
                    BookId = book.Id,
                    BatchId = batch.BatchId,
                    Title = TextNormalizer.NormalizeName(section.Title),
                    Kind = string.IsNullOrWhiteSpace(section.Kind) ? "section" : section.Kind,
                    PageStart = section.PageStart,
                    PageEnd = section.PageEnd,
                    Summary = section.Summary,
                    Body = TextNormalizer.CleanBody(section.Body),
                });
                report.Sections++;
            }

            foreach (var extracted in batch.Elements)
            {
                var kind = extracted.Kind.Trim().ToLowerInvariant();
                var name = TextNormalizer.NormalizeName(extracted.Name);
                if (string.IsNullOrWhiteSpace(kind) || string.IsNullOrWhiteSpace(name))
                {
                    report.Warnings.Add($"Skipped element with missing kind/name in batch {batch.BatchId}.");
                    continue;
                }

                var slug = string.IsNullOrWhiteSpace(extracted.Slug)
                    ? TextNormalizer.Slugify($"{kind}-{name}")
                    : TextNormalizer.Slugify(extracted.Slug);
                var unique = slug;
                var n = 2;
                while (!usedSlugs.Add($"{kind}:{unique}"))
                {
                    unique = $"{slug}-{n++}";
                }

                string? dataJson = null;
                if (extracted.Data is { ValueKind: JsonValueKind.Object or JsonValueKind.Array })
                {
                    dataJson = extracted.Data.Value.GetRawText();
                }

                var element = new GameElement
                {
                    BookId = book.Id,
                    Kind = kind,
                    Slug = unique,
                    Name = name,
                    Subtitle = extracted.Subtitle,
                    PageStart = extracted.PageStart,
                    PageEnd = extracted.PageEnd,
                    Summary = extracted.Summary,
                    Body = TextNormalizer.CleanBody(extracted.Body),
                    DataJson = dataJson,
                };

                foreach (var tag in extracted.Tags.Where(t => !string.IsNullOrWhiteSpace(t)).Distinct(StringComparer.OrdinalIgnoreCase))
                {
                    element.Tags.Add(new GameElementTag { Tag = tag.Trim().ToLowerInvariant() });
                    report.Tags++;
                }

                if (!string.IsNullOrWhiteSpace(extracted.ParentKind) && !string.IsNullOrWhiteSpace(extracted.ParentName))
                {
                    pendingParents.Add((element, extracted.ParentKind!, TextNormalizer.NormalizeName(extracted.ParentName)));
                }

                foreach (var link in extracted.SeeAlso)
                {
                    pendingRefs.Add((element, link));
                }

                _db.GameElements.Add(element);
                report.Elements++;
            }
        }

        _db.SaveChanges();

        var byKindName = _db.GameElements
            .Where(e => e.BookId == book.Id)
            .AsEnumerable()
            .GroupBy(e => Key(e.Kind, e.Name))
            .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);

        foreach (var (element, parentKind, parentName) in pendingParents)
        {
            if (byKindName.TryGetValue(Key(parentKind, parentName), out var parent))
            {
                element.ParentElementId = parent.Id;
            }
            else
            {
                report.Warnings.Add($"Parent not found: {parentKind}/{parentName} for {element.Kind}/{element.Name}.");
            }
        }

        foreach (var (from, link) in pendingRefs)
        {
            var targetKind = string.IsNullOrWhiteSpace(link.Kind) ? "" : link.Kind.Trim().ToLowerInvariant();
            var targetName = TextNormalizer.NormalizeName(link.Name);
            int? toId = null;
            if (!string.IsNullOrWhiteSpace(targetKind) && byKindName.TryGetValue(Key(targetKind, targetName), out var to))
            {
                toId = to.Id;
            }

            _db.CrossRefs.Add(new CrossRef
            {
                FromElementId = from.Id,
                TargetKind = targetKind,
                TargetName = targetName,
                ToElementId = toId,
                Relation = string.IsNullOrWhiteSpace(link.Relation) ? "see_also" : link.Relation,
            });
            report.CrossRefs++;
        }

        _db.SaveChanges();
        _db.RebuildSearchIndex();
        return report;
    }

    private void ImportOutline(Book book, IReadOnlyList<TocEntry> toc, ImportReport report)
    {
        if (toc.Count == 0)
        {
            return;
        }

        var stack = new List<OutlineEntry>();
        for (var i = 0; i < toc.Count; i++)
        {
            var entry = toc[i];
            var pageEnd = i + 1 < toc.Count ? Math.Max(entry.Page, toc[i + 1].Page) : book.PageCount;
            var row = new OutlineEntry
            {
                BookId = book.Id,
                Level = entry.Level,
                Title = TextNormalizer.NormalizeName(entry.Title),
                PageStart = entry.Page,
                PageEnd = pageEnd,
                SortOrder = i,
            };

            while (stack.Count > 0 && stack[^1].Level >= entry.Level)
            {
                stack.RemoveAt(stack.Count - 1);
            }

            if (stack.Count > 0)
            {
                row.Parent = stack[^1];
            }

            stack.Add(row);
            _db.OutlineEntries.Add(row);
            report.OutlineEntries++;
        }

        _db.SaveChanges();
    }

    private static string Key(string kind, string name) =>
        $"{kind.Trim().ToLowerInvariant()}|{TextNormalizer.NormalizeName(name)}";
}
