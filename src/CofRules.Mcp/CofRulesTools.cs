using System.ComponentModel;
using System.Text.Json;
using CofRules.Core;
using ModelContextProtocol.Server;

namespace CofRules.Mcp;

[McpServerToolType]
public sealed class CofRulesTools(RulesCatalog catalog)
{
    [McpServerTool(Name = "cof_stats"), Description("Statistiques du catalogue COF2 (livres, comptages par type).")]
    public string Stats() => Serialize(catalog.Stats());

    [McpServerTool(Name = "cof_list_books"), Description("Livres de référence indexés (slug, titre, alias).")]
    public string ListBooks() => Serialize(catalog.ListBooks().Select(b => new
    {
        b.Id,
        b.Slug,
        b.Title,
        b.Edition,
        page_count = b.PageCount,
        aliases = JsonSerializer.Deserialize<string[]>(b.AliasesJson),
    }));

    [McpServerTool(Name = "cof_search"), Description("Recherche souple : par nom (accents/casse ignorés) ou par livre + page, ex. 'livre de base page 345', 'demi-elfe', 'nain'.")]
    public string Search(
        [Description("Requête libre : nom ('arquebusier') ou référence ('livre de base page 345', 'p. 48')")] string query,
        [Description("Livre de référence optionnel (slug ou alias, ex. livre-de-base)")] string? book = null,
        [Description("Numéro de page du livre, si déjà connu")] int? page = null,
        [Description("Filtre de type : people, profile, voie, capacity, creature, equipment, rule, magic_item, spell…")] string? kind = null,
        [Description("Nombre max de résultats (1-50)")] int limit = 20)
        => Serialize(catalog.Search(query, limit, book, page, kind));

    [McpServerTool(Name = "cof_get_page"), Description("Tous les éléments et sections d'une page d'un livre (ex. livre=livre-de-base, page=345).")]
    public string GetPage(
        [Description("Numéro de page")] int page,
        [Description("Livre (défaut : livre de base)")] string? book = "livre de base")
        => Serialize(catalog.Search("", 50, book, page));

    [McpServerTool(Name = "cof_list_outline"), Description("Sommaire hiérarchique d'un livre.")]
    public string ListOutline([Description("Livre optionnel")] string? book = null)
    {
        var rows = catalog.ListOutline(book).Select(o => new
        {
            o.Id,
            o.Level,
            o.Title,
            page_start = o.PageStart,
            page_end = o.PageEnd,
            parent_id = o.ParentId,
        });
        return Serialize(rows);
    }

    [McpServerTool(Name = "cof_list_elements"), Description("Liste des éléments de jeu, filtrable par kind et nom souple.")]
    public string ListElements(
        [Description("Type d'élément")] string? kind = null,
        [Description("Filtre sur le nom")] string? query = null,
        [Description("Livre optionnel")] string? book = null,
        [Description("Limite")] int limit = 50)
        => Serialize(catalog.ListElements(kind, query, limit, book).Select(Summarize));

    [McpServerTool(Name = "cof_get_element"), Description("Fiche complète d'un élément (corps Markdown + JSON structuré + enfants).")]
    public string GetElement(
        [Description("Nom ou slug (recherche souple)")] string name,
        [Description("Type optionnel pour désambiguïser")] string? kind = null,
        [Description("Livre optionnel")] string? book = null)
    {
        var element = catalog.GetElement(name, kind, book);
        return element == null ? Serialize(new { error = "not_found", name, kind }) : Serialize(Detail(element));
    }

    [McpServerTool(Name = "cof_list_peoples"), Description("Liste des peuples jouables.")]
    public string ListPeoples([Description("Filtre nom")] string? query = null)
        => Serialize(catalog.ListElements("people", query, 100).Select(Summarize));

    [McpServerTool(Name = "cof_get_people"), Description("Détail d'un peuple (traits, caractéristiques, voie).")]
    public string GetPeople([Description("Nom du peuple, ex. Nain")] string name) => GetElement(name, "people");

    [McpServerTool(Name = "cof_list_profiles"), Description("Liste des profils (classes) : aventuriers, combattants, mages, mystiques.")]
    public string ListProfiles(
        [Description("Filtre nom")] string? query = null,
        [Description("Filtre famille optionnel")] string? family = null)
    {
        var rows = catalog.ListElements("profile", query, 100);
        if (!string.IsNullOrWhiteSpace(family))
        {
            rows = rows.Where(p => p.DataJson != null && p.DataJson.Contains(family, StringComparison.OrdinalIgnoreCase)).ToList();
        }

        return Serialize(rows.Select(Summarize));
    }

    [McpServerTool(Name = "cof_get_profile"), Description("Détail d'un profil avec ses voies et capacités enfants.")]
    public string GetProfile([Description("Nom du profil, ex. Arquebusier")] string name) => GetElement(name, "profile");

    [McpServerTool(Name = "cof_list_voies"), Description("Liste des voies (profil, peuple ou prestige).")]
    public string ListVoies([Description("Filtre nom")] string? query = null)
        => Serialize(catalog.ListElements("voie", query, 200).Select(Summarize));

    [McpServerTool(Name = "cof_get_voie"), Description("Détail d'une voie et de ses capacités par rang.")]
    public string GetVoie([Description("Nom de la voie")] string name) => GetElement(name, "voie");

    [McpServerTool(Name = "cof_list_creatures"), Description("Liste des créatures / opposition.")]
    public string ListCreatures([Description("Filtre nom")] string? query = null)
        => Serialize(catalog.ListElements("creature", query, 200).Select(Summarize));

    [McpServerTool(Name = "cof_get_creature"), Description("Fiche technique d'une créature (NC, stats, attaques, capacités).")]
    public string GetCreature([Description("Nom, ex. Assassin")] string name) => GetElement(name, "creature");

    [McpServerTool(Name = "cof_list_equipment"), Description("Liste de l'équipement (armes, armures, matériel).")]
    public string ListEquipment([Description("Filtre nom")] string? query = null)
        => Serialize(catalog.ListElements("equipment", query, 200).Select(Summarize));

    [McpServerTool(Name = "cof_list_magic_items"), Description("Liste des objets magiques.")]
    public string ListMagicItems([Description("Filtre nom")] string? query = null)
        => Serialize(catalog.ListElements("magic_item", query, 200).Select(Summarize));

    [McpServerTool(Name = "cof_get_section"), Description("Texte d'une section extraite (chapitre ou sous-partie).")]
    public string GetSection(
        [Description("Titre de section")] string title,
        [Description("Livre optionnel")] string? book = null)
    {
        var section = catalog.GetSection(title, book);
        return section == null
            ? Serialize(new { error = "not_found", title })
            : Serialize(new
            {
                section.Id,
                section.Title,
                section.Kind,
                section.BatchId,
                page_start = section.PageStart,
                page_end = section.PageEnd,
                section.Summary,
                section.Body,
                book = section.Book.Slug,
            });
    }

    [McpServerTool(Name = "cof_list_sections"), Description("Liste des sections. Filtrer par page PDF ou batch_id.")]
    public string ListSections(
        [Description("Numéro de page du livre")] int? page = null,
        [Description("Identifiant de lot d'extraction")] string? batch_id = null,
        [Description("Livre optionnel")] string? book = null)
        => Serialize(catalog.ListSections(page, batch_id, book).Select(s => new
        {
            s.Id,
            s.Title,
            s.Kind,
            s.BatchId,
            page_start = s.PageStart,
            page_end = s.PageEnd,
            s.Summary,
        }));

    private static object Summarize(GameElement e) => new
    {
        e.Id,
        e.Kind,
        e.Slug,
        e.Name,
        e.Subtitle,
        page_start = e.PageStart,
        page_end = e.PageEnd,
        e.Summary,
        book = e.Book.Slug,
        tags = e.Tags.Select(t => t.Tag).ToArray(),
    };

    private static object Detail(GameElement e)
    {
        object? data = null;
        if (!string.IsNullOrWhiteSpace(e.DataJson))
        {
            data = JsonSerializer.Deserialize<JsonElement>(e.DataJson);
        }

        return new
        {
            e.Id,
            e.Kind,
            e.Slug,
            e.Name,
            e.Subtitle,
            page_start = e.PageStart,
            page_end = e.PageEnd,
            e.Summary,
            e.Body,
            data,
            book = e.Book.Slug,
            tags = e.Tags.Select(t => t.Tag).ToArray(),
            parent = e.Parent == null ? null : new { e.Parent.Kind, e.Parent.Name, e.Parent.Slug },
            children = e.Children.OrderBy(c => c.PageStart).ThenBy(c => c.Name).Select(c => new
            {
                c.Kind,
                c.Name,
                c.Slug,
                page_start = c.PageStart,
                c.Summary,
            }),
            see_also = e.Outgoing.Select(r => new { r.Relation, r.TargetKind, r.TargetName, r.ToElementId }),
        };
    }

    private static string Serialize(object value) => JsonSerializer.Serialize(value, JsonDefaults.Compact);
}
