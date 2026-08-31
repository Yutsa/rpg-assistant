namespace CofRules.Core;

public static class AppPaths
{
    public static string RepoRoot
    {
        get
        {
            var dir = new DirectoryInfo(Directory.GetCurrentDirectory());
            for (var i = 0; i < 10 && dir != null; i++, dir = dir.Parent)
            {
                if (IsRepoRoot(dir))
                {
                    return dir.FullName;
                }
            }

            dir = new DirectoryInfo(AppContext.BaseDirectory);
            for (var i = 0; i < 12 && dir != null; i++, dir = dir.Parent)
            {
                if (IsRepoRoot(dir))
                {
                    return dir.FullName;
                }
            }

            return Directory.GetCurrentDirectory();
        }
    }

    public static string ExtractRoot => Path.Combine(RepoRoot, "extract");
    public static string StructuredRoot => Path.Combine(ExtractRoot, "structured");
    public static string TocPath => Path.Combine(ExtractRoot, "toc.json");
    public static string BatchesPath => Path.Combine(ExtractRoot, "batches.json");

    public static string DefaultDbPath =>
        Environment.GetEnvironmentVariable("COF_RULES_DB")
        ?? Path.Combine(RepoRoot, "data", "cof_rules.db");

    private static bool IsRepoRoot(DirectoryInfo dir) =>
        File.Exists(Path.Combine(dir.FullName, "CofRules.slnx"))
        || File.Exists(Path.Combine(dir.FullName, "CofRules.sln"));
}
