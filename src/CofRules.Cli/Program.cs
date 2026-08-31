using System.Text.Json;
using CofRules.Core;

if (args.Length == 0)
{
    PrintHelp();
    return 1;
}

var command = args[0].ToLowerInvariant();
return command switch
{
    "import" => RunImport(args.Skip(1).ToArray()),
    "stats" => RunStats(),
    "search" => RunSearch(args.Skip(1).ToArray()),
    _ => Fail($"Unknown command '{command}'."),
};

static int RunImport(string[] args)
{
    var extract = AppPaths.ExtractRoot;
    var dbPath = AppPaths.DefaultDbPath;
    for (var i = 0; i < args.Length; i++)
    {
        if (args[i] == "--extract" && i + 1 < args.Length) extract = args[++i];
        else if (args[i] == "--db" && i + 1 < args.Length) dbPath = args[++i];
    }

    using var db = CofRulesDbContext.Open(dbPath);
    var report = StructuredLoader.ImportFromExtract(db, extract);
    report.DatabasePath = dbPath;
    Console.WriteLine(JsonSerializer.Serialize(report, JsonDefaults.Options));
    return report.Elements == 0 ? 2 : 0;
}

static int RunStats()
{
    using var db = CofRulesDbContext.Open(AppPaths.DefaultDbPath);
    var catalog = new RulesCatalog(db);
    Console.WriteLine(JsonSerializer.Serialize(catalog.Stats(), JsonDefaults.Compact));
    return 0;
}

static int RunSearch(string[] args)
{
    var query = string.Join(" ", args);
    using var db = CofRulesDbContext.Open(AppPaths.DefaultDbPath);
    var catalog = new RulesCatalog(db);
    var hits = catalog.Search(query);
    Console.WriteLine(JsonSerializer.Serialize(hits, JsonDefaults.Options));
    return 0;
}

static int Fail(string message)
{
    Console.Error.WriteLine(message);
    PrintHelp();
    return 1;
}

static void PrintHelp()
{
    Console.Error.WriteLine("""
        CofRules.Cli
          import [--extract DIR] [--db PATH]   Import structured JSON into SQLite
          stats                                Print catalog counts
          search <query>                       Search by name or "livre de base page 345"
        """);
}
