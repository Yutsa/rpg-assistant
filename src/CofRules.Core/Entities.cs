namespace CofRules.Core;

public sealed class Book
{
    public int Id { get; set; }
    public string Slug { get; set; } = "";
    public string Title { get; set; } = "";
    public string Edition { get; set; } = "";
    public int PageCount { get; set; }
    public string AliasesJson { get; set; } = "[]";
    public string? SourcePath { get; set; }
    public DateTimeOffset ImportedAt { get; set; } = DateTimeOffset.UtcNow;
    public ICollection<OutlineEntry> Outline { get; set; } = new List<OutlineEntry>();
    public ICollection<Section> Sections { get; set; } = new List<Section>();
    public ICollection<GameElement> Elements { get; set; } = new List<GameElement>();
}

public sealed class OutlineEntry
{
    public int Id { get; set; }
    public int BookId { get; set; }
    public Book Book { get; set; } = null!;
    public int? ParentId { get; set; }
    public OutlineEntry? Parent { get; set; }
    public int Level { get; set; }
    public string Title { get; set; } = "";
    public int PageStart { get; set; }
    public int PageEnd { get; set; }
    public int SortOrder { get; set; }
}

public sealed class Section
{
    public int Id { get; set; }
    public int BookId { get; set; }
    public Book Book { get; set; } = null!;
    public string BatchId { get; set; } = "";
    public string Title { get; set; } = "";
    public string TitleNormalized { get; set; } = "";
    public string Kind { get; set; } = "section";
    public int PageStart { get; set; }
    public int PageEnd { get; set; }
    public string? Summary { get; set; }
    public string Body { get; set; } = "";
}

public sealed class GameElement
{
    public int Id { get; set; }
    public int BookId { get; set; }
    public Book Book { get; set; } = null!;
    public int? ParentElementId { get; set; }
    public GameElement? Parent { get; set; }
    public ICollection<GameElement> Children { get; set; } = new List<GameElement>();
    public string Kind { get; set; } = "";
    public string Slug { get; set; } = "";
    public string Name { get; set; } = "";
    public string NameNormalized { get; set; } = "";
    public string? Subtitle { get; set; }
    public int PageStart { get; set; }
    public int PageEnd { get; set; }
    public string? Summary { get; set; }
    public string Body { get; set; } = "";
    public string? DataJson { get; set; }
    public ICollection<GameElementTag> Tags { get; set; } = new List<GameElementTag>();
    public ICollection<CrossRef> Outgoing { get; set; } = new List<CrossRef>();
}

public sealed class GameElementTag
{
    public int GameElementId { get; set; }
    public GameElement GameElement { get; set; } = null!;
    public string Tag { get; set; } = "";
}

public sealed class CrossRef
{
    public int FromElementId { get; set; }
    public GameElement From { get; set; } = null!;
    public string TargetKind { get; set; } = "";
    public string TargetName { get; set; } = "";
    public int? ToElementId { get; set; }
    public GameElement? To { get; set; }
    public string Relation { get; set; } = "see_also";
}
