using System.Text.Json;

namespace CofRules.Core;

public static class StructuredLoader
{
    public static IReadOnlyList<ExtractionBatch> LoadDirectory(string directory)
    {
        if (!Directory.Exists(directory))
        {
            return [];
        }

        var files = Directory.GetFiles(directory, "*.json").OrderBy(f => f, StringComparer.OrdinalIgnoreCase);
        var batches = new List<ExtractionBatch>();
        foreach (var file in files)
        {
            var json = File.ReadAllText(file);
            var batch = JsonSerializer.Deserialize<ExtractionBatch>(json, JsonDefaults.Options);
            if (batch == null || string.IsNullOrWhiteSpace(batch.BatchId))
            {
                throw new InvalidDataException($"Invalid extraction batch: {file}");
            }

            batches.Add(batch);
        }

        return batches;
    }

    public static IReadOnlyList<TocEntry> LoadToc(string path)
    {
        if (!File.Exists(path))
        {
            return [];
        }

        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<List<TocEntry>>(json, JsonDefaults.Options) ?? [];
    }

    public static ImportReport ImportFromExtract(CofRulesDbContext db, string? extractRoot = null, string? sourcePdf = null)
    {
        extractRoot ??= AppPaths.ExtractRoot;
        var batches = LoadDirectory(Path.Combine(extractRoot, "structured"));
        var toc = LoadToc(Path.Combine(extractRoot, "toc.json"));
        var meta = new BookMeta { SourcePath = sourcePdf ?? "data/pdfs/COF_Livre_Regles.pdf" };
        return new RulesImporter(db).Import(batches, toc, meta);
    }
}
