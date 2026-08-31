using CofRules.Core;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace CofRules.Tests;

public sealed class CatalogTests : IDisposable
{
    private readonly SqliteConnection _connection;
    private readonly CofRulesDbContext _db;

    public CatalogTests()
    {
        _connection = new SqliteConnection("Data Source=:memory:");
        _connection.Open();
        var options = new DbContextOptionsBuilder<CofRulesDbContext>()
            .UseSqlite(_connection)
            .Options;
        _db = new CofRulesDbContext(options);
        _db.Database.EnsureCreated();
        _db.EnsureSearchIndex();
    }

    [Fact]
    public void QueryParser_DetectsBookAndPage()
    {
        var parsed = QueryParser.Parse("livre de base page 345");
        Assert.Equal(345, parsed.Page);
        Assert.Equal("livre de base", parsed.BookHint);
        Assert.True(parsed.IsPageLookup);

        var pDot = QueryParser.Parse("p.48");
        Assert.Equal(48, pDot.Page);

        var name = QueryParser.Parse("demi-elfe");
        Assert.Null(name.Page);
        Assert.Equal("demi-elfe", name.NameQuery);
    }

    [Fact]
    public void Import_IndexesPeopleAndSearch()
    {
        var batch = new ExtractionBatch
        {
            BatchId = "03-peuples",
            PageStart = 44,
            PageEnd = 60,
            Sections =
            [
                new ExtractedSection
                {
                    Title = "Peuples",
                    Kind = "chapter",
                    PageStart = 44,
                    PageEnd = 44,
                    Body = "Huit peuples.",
                },
            ],
            Elements =
            [
                new ExtractedElement
                {
                    Kind = "people",
                    Name = "Demi-elfe",
                    PageStart = 45,
                    PageEnd = 46,
                    Summary = "Héritage humain et elfe.",
                    Body = "+1 PER ou CHA, -1 FOR ou CON",
                    Tags = ["peuple"],
                },
                new ExtractedElement
                {
                    Kind = "profile",
                    Name = "Arquebusier",
                    PageStart = 62,
                    PageEnd = 65,
                    Summary = "Spécialiste des armes à poudre.",
                    Body = "PV 4/niveau, DR d8.",
                    Tags = ["aventuriers"],
                },
                new ExtractedElement
                {
                    Kind = "voie",
                    Name = "Voie de l'artilleur",
                    PageStart = 62,
                    PageEnd = 63,
                    Body = "Voie d'arquebusier.",
                    ParentKind = "profile",
                    ParentName = "Arquebusier",
                },
            ],
        };

        var toc = new List<TocEntry>
        {
            new() { Level = 3, Page = 44, Title = "Peuples" },
        };

        var report = new RulesImporter(_db).Import([batch], toc, new BookMeta { PageCount = 90 });
        Assert.Equal(3, report.Elements);
        Assert.Equal("livre-de-base", report.BookSlug);

        var catalog = new RulesCatalog(_db);
        var people = catalog.GetElement("demi elfe", "people");
        Assert.NotNull(people);
        Assert.Contains("PER", people!.Body);

        var nameHits = catalog.Search("demi-elfe");
        Assert.Equal("name", nameHits.Mode);
        Assert.Contains(nameHits.Hits, h => h.Name == "Demi-elfe");

        var pageHits = catalog.Search("livre de base page 45");
        Assert.Equal("page", pageHits.Mode);
        Assert.Equal(45, pageHits.Page);
        Assert.Contains(pageHits.Hits, h => h.Name == "Demi-elfe");

        var byPageTool = catalog.Search("", book: "livre-de-base", page: 62);
        Assert.Contains(byPageTool.Hits, h => h.Name == "Arquebusier");

        var voie = catalog.GetElement("voie de l artilleur", "voie");
        Assert.NotNull(voie);
        Assert.Equal(catalog.GetElement("arquebusier", "profile")!.Id, voie!.ParentElementId);
    }

    [Fact]
    public void Import_RealExtract_LoadsLivreDeBase()
    {
        var extract = Path.Combine(AppPaths.RepoRoot, "extract");
        Assert.True(Directory.Exists(Path.Combine(extract, "structured")));

        var report = StructuredLoader.ImportFromExtract(_db, extract);
        Assert.True(report.Elements > 100, $"expected a full extract, got {report.Elements} elements");
        Assert.Equal("livre-de-base", report.BookSlug);

        var catalog = new RulesCatalog(_db);
        var nain = catalog.GetElement("nain", "people");
        Assert.NotNull(nain);
        Assert.InRange(nain!.PageStart, 1, 358);

        var pageSearch = catalog.Search("livre de base page 48");
        Assert.Equal("page", pageSearch.Mode);
        Assert.NotEmpty(pageSearch.Hits);

        var nameSearch = catalog.Search("demi-elfe");
        Assert.Equal("Demi-elfe", nameSearch.Hits[0].Name);
    }

    [Fact]
    public void TextNormalizer_StripsWatermarkAndFolds()
    {
        var raw = "Hello\nÉdouard WILLISSECK - edouard.willisseck@gmail.com - 202608/1\nWorld";
        Assert.DoesNotContain("WILLISSECK", TextNormalizer.CleanBody(raw));
        Assert.Equal("voie-de-l-artilleur", TextNormalizer.Slugify("Voie de l'artilleur"));
        Assert.Equal("demi elfe", TextNormalizer.Fold("Demi-elfe"));
    }

    public void Dispose()
    {
        _db.Dispose();
        _connection.Dispose();
    }
}
