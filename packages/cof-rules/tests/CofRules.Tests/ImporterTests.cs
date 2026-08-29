using CofRules.Core;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace CofRules.Tests;

public sealed class ImporterTests : IDisposable
{
    private readonly SqliteConnection _connection;
    private readonly CofRulesDbContext _db;

    public ImporterTests()
    {
        _connection = new SqliteConnection("Data Source=:memory:");
        _connection.Open();
        var options = new DbContextOptionsBuilder<CofRulesDbContext>().UseSqlite(_connection).Options;
        _db = new CofRulesDbContext(options);
        _db.Database.EnsureCreated();
        _db.EnsureSearchIndex();
    }

    [Fact]
    public void Import_PersistsPeopleProfileAndNestedCapacity()
    {
        var batch = new ExtractionBatch
        {
            BatchId = "test",
            PageStart = 44,
            PageEnd = 63,
            Sections =
            [
                new ExtractedSection
                {
                    Title = "Peuples",
                    Kind = "chapter",
                    PageStart = 44,
                    PageEnd = 60,
                    Summary = "Peuples jouables",
                    Body = "Les peuples définissent l'origine du personnage.",
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
                    Data = JsonData("""{"stat_modifiers":{"PER":1,"CHA":1}}"""),
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
                    Kind = "capacity",
                    Name = "Mécanismes",
                    PageStart = 62,
                    PageEnd = 62,
                    Body = "Ajoute rang + 2 aux tests de mécanismes.",
                    ParentKind = "voie",
                    ParentName = "Voie de l'artilleur",
                    SeeAlso = [new ExtractedSeeAlso { Kind = "profile", Name = "Arquebusier", Relation = "belongs_to" }],
                },
            ],
        };

        var toc = new List<TocEntry>
        {
            new() { Level = 3, Page = 44, Title = "Peuples" },
            new() { Level = 3, Page = 61, Title = "Famille des aventuriers" },
        };

        var report = new RulesImporter(_db).Import([batch], toc, new BookMeta { PageCount = 90 });
        Assert.Equal(1, report.Sections);
        Assert.Equal(4, report.Elements);
        Assert.Equal(2, report.OutlineEntries);

        var catalog = new RulesCatalog(_db);
        var people = catalog.GetElement("Demi-elfe", "people");
        Assert.NotNull(people);
        Assert.Contains("PER", people!.Body);

        var profile = catalog.GetElement("arquebusier", "profile");
        Assert.NotNull(profile);

        var voie = catalog.GetElement("Voie de l'artilleur", "voie");
        Assert.NotNull(voie);
        Assert.Equal(profile!.Id, voie!.ParentElementId);

        var capacity = catalog.GetElement("Mécanismes", "capacity");
        Assert.NotNull(capacity);
        Assert.Equal(voie.Id, capacity!.ParentElementId);

        var hits = catalog.Search("Mécanismes");
        Assert.Contains(hits, h => h.Name == "Mécanismes");
    }

    [Fact]
    public void TextNormalizer_StripsWatermarkAndSlugifies()
    {
        var raw = "Hello\nÉdouard WILLISSECK - edouard.willisseck@gmail.com - 202608/1\nWorld";
        Assert.DoesNotContain("WILLISSECK", TextNormalizer.CleanBody(raw));
        Assert.Equal("voie-de-l-artilleur", TextNormalizer.Slugify("Voie de l'artilleur"));
    }

    private static System.Text.Json.JsonElement JsonData(string json) =>
        System.Text.Json.JsonDocument.Parse(json).RootElement.Clone();

    public void Dispose()
    {
        _db.Dispose();
        _connection.Dispose();
    }
}
