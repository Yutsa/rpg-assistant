namespace CofRules.Core;

public static class AppPaths
{
    public static string RepoRoot
    {
        get
        {
            var dir = new DirectoryInfo(Directory.GetCurrentDirectory());
            for (var i = 0; i < 8 && dir != null; i++, dir = dir.Parent)
            {
                if (File.Exists(Path.Combine(dir.FullName, "packages", "cof-rules", "CofRules.sln"))
                    || File.Exists(Path.Combine(dir.FullName, "pyproject.toml")))
                {
                    return dir.FullName;
                }
            }

            dir = new DirectoryInfo(AppContext.BaseDirectory);
            for (var i = 0; i < 10 && dir != null; i++, dir = dir.Parent)
            {
                if (File.Exists(Path.Combine(dir.FullName, "CofRules.sln")))
                {
                    return dir.Parent?.Parent?.FullName ?? dir.FullName;
                }
            }

            return Directory.GetCurrentDirectory();
        }
    }

    public static string PackageRoot => Path.Combine(RepoRoot, "packages", "cof-rules");
    public static string ExtractRoot => Path.Combine(PackageRoot, "extract");
    public static string StructuredRoot => Path.Combine(ExtractRoot, "structured");
    public static string TocPath => Path.Combine(ExtractRoot, "toc.json");
    public static string DefaultDbPath =>
        Environment.GetEnvironmentVariable("COF_RULES_DB")
        ?? Path.Combine(RepoRoot, "data", "cof_rules.db");
}
