using System.ComponentModel;
using System.Text.Json;
using CofRules.Core;
using ModelContextProtocol.Server;

namespace CofRules.Mcp;

[McpServerToolType]
public sealed class CofRulesTools(RulesCatalog catalog)
{
    [McpServerTool(Name = "cof_stats"), Description("Statistiques du livre de règles COF importé (comptages par type).")]
    public string Stats() => Serialize(catalog.Stats());

    [McpServerTool(Name = "cof_list_outline"), Description("Sommaire hiérarchique du livre de règles Chroniques Oubliées Fantasy.")]
    public string ListOutline()
    {
        var rows = catalog.ListOutline().Select(o => new
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

    [McpServerTool(Name = "cof_search"), Description("Recherche plein texte dans les règles, profils, peuples, créatures, voies et capacités.")]
    public string Search(
        [Description("Mots-clés (ex. 'attaque surprise', 'demi-elfe', 'couleuvrine')")] string query,
        [Description("Nombre max de résultats (1-50)")] int limit = 20)
        => Serialize(catalog.Search(query, limit));

    [McpServerTool(Name = "cof_list_elements"), Description("Liste des éléments de jeu, filtrable par kind (people, profile, voie, capacity, creature, equipment, rule, magic_item, spell, scenario, npc, table, setting, glossary_term).")]
    public string ListElements(
        [Description("Type d'élément")] string? kind = null,
        [Description("Filtre sur le nom")] string? query = null,
        [Description("Limite")] int limit = 50)
        => Serialize(catalog.ListElements(kind, query, limit).Select(Summarize));

    [McpServerTool(Name = "cof_get_element"), Description("Fiche complète d'un élément (corps Markdown + JSON structuré + enfants).")]
    public string GetElement(
        [Description("Nom ou slug")] string name,
        [Description("Type optionnel pour désambiguïser")] string? kind = null)
    {
        var element = catalog.GetElement(name, kind);
        return element == null ? Serialize(new { error = "not_found", name, kind }) : Serialize(Detail(element));
    }

    [McpServerTool(Name = "cof_list_peoples"), Description("Liste des peuples jouables.")]
    public string ListPeoples() => Serialize(catalog.ListElements("people", limit: 100).Select(Summarize));

    [McpServerTool(Name = "cof_get_people"), Description("Détail d'un peuple (traits, caractéristiques, voie).")]
    public string GetPeople([Description("Nom du peuple, ex. Nain")] string name) => GetElement(name, "people");

    [McpServerTool(Name = "cof_list_profiles"), Description("Liste des profils (classes) : aventuriers, combattants, mages, mystiques.")]
    public string ListProfiles([Description("Filtre famille optionnel")] string? family = null)
    {
        var rows = catalog.ListElements("profile", limit: 100);
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
    public string GetSection([Description("Titre de section")] string title)
    {
        var section = catalog.GetSection(title);
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
            });
    }

    [McpServerTool(Name = "cof_list_sections"), Description("Liste des sections. Filtrer par page PDF ou batch_id.")]
    public string ListSections(
        [Description("Numéro de page du livre")] int? page = null,
        [Description("Identifiant de lot d'extraction")] string? batch_id = null)
        => Serialize(catalog.ListSections(page, batch_id).Select(s => new
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
