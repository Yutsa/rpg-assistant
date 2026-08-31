using CofRules.Core;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.AddConsole(options =>
{
    options.LogToStandardErrorThreshold = LogLevel.Trace;
});

var dbPath = AppPaths.DefaultDbPath;
var db = CofRulesDbContext.Open(dbPath);
if (!db.GameElements.Any() && Directory.Exists(AppPaths.StructuredRoot))
{
    StructuredLoader.ImportFromExtract(db);
}

builder.Services.AddSingleton(db);
builder.Services.AddSingleton<RulesCatalog>();
builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithTools<CofRules.Mcp.CofRulesTools>();

await builder.Build().RunAsync();
