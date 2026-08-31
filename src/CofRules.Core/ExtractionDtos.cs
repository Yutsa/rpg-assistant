using System.Text.Json;
using System.Text.Json.Serialization;

namespace CofRules.Core;

public sealed class ExtractionBatch
{
    [JsonPropertyName("batch_id")]
    public string BatchId { get; set; } = "";

    [JsonPropertyName("page_start")]
    public int PageStart { get; set; }

    [JsonPropertyName("page_end")]
    public int PageEnd { get; set; }

    [JsonPropertyName("notes")]
    public string? Notes { get; set; }

    [JsonPropertyName("sections")]
    public List<ExtractedSection> Sections { get; set; } = [];

    [JsonPropertyName("elements")]
    public List<ExtractedElement> Elements { get; set; } = [];
}

public sealed class ExtractedSection
{
    public string Title { get; set; } = "";
    public string Kind { get; set; } = "section";
    [JsonPropertyName("page_start")]
    public int PageStart { get; set; }
    [JsonPropertyName("page_end")]
    public int PageEnd { get; set; }
    public string? Summary { get; set; }
    public string Body { get; set; } = "";
}

public sealed class ExtractedElement
{
    public string Kind { get; set; } = "";
    public string Name { get; set; } = "";
    public string? Slug { get; set; }
    public string? Subtitle { get; set; }
    [JsonPropertyName("page_start")]
    public int PageStart { get; set; }
    [JsonPropertyName("page_end")]
    public int PageEnd { get; set; }
    public string? Summary { get; set; }
    public string Body { get; set; } = "";
    public List<string> Tags { get; set; } = [];
    [JsonPropertyName("parent_kind")]
    public string? ParentKind { get; set; }
    [JsonPropertyName("parent_name")]
    public string? ParentName { get; set; }
    public JsonElement? Data { get; set; }
    [JsonPropertyName("see_also")]
    public List<ExtractedSeeAlso> SeeAlso { get; set; } = [];
}

public sealed class ExtractedSeeAlso
{
    public string? Kind { get; set; }
    public string Name { get; set; } = "";
    public string Relation { get; set; } = "see_also";
}

public sealed class TocEntry
{
    public int Level { get; set; }
    public int Page { get; set; }
    public string Title { get; set; } = "";
}

public sealed class BatchesFile
{
    public BookMeta Book { get; set; } = new();
}

public sealed class BookMeta
{
    public string Title { get; set; } = "Chroniques Oubliées Fantasy — Livre de base";
    public string Edition { get; set; } = "2e impression Mai 2025";
    [JsonPropertyName("page_count")]
    public int PageCount { get; set; } = 358;
    public string Slug { get; set; } = "livre-de-base";
    public string[] Aliases { get; set; } =
    [
        "livre de base",
        "ldb",
        "cof",
        "cof2",
        "chroniques oubliees",
        "chroniques oubliées",
        "chroniques oubliées fantasy",
        "livre de regles",
        "livre de règles",
        "regles",
        "règles",
    ];
    public string? SourcePath { get; set; }
}
