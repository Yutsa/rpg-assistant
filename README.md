# COF Rules MCP

Serveur MCP (.NET 10) pour interroger le **livre de base Chroniques Oubliées Fantasy 2** : règles, peuples, profils, voies, capacités, équipement, créatures.

La recherche se fait :

- **par nom**, de façon souple (casse et accents ignorés) : `nain`, `demi-elfe`, `arquebusier` ;
- **par livre + page** : `livre de base page 345`, `p. 48`, ou les arguments MCP `book` + `page`.

Les extraits structurés du livre de base vivent dans `extract/structured/` et sont importés dans une base **SQLite** (`data/cof_rules.db`, FTS5).

## Prérequis

- SDK [.NET 10](https://dotnet.microsoft.com/download)

```bash
# optionnel, user-local
curl -sSL https://dot.net/v1/dotnet-install.sh | bash /dev/stdin --channel 10.0
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$DOTNET_ROOT:$PATH"
```

## Importer le livre de base

```bash
dotnet test CofRules.slnx
dotnet run --project src/CofRules.Cli -- import
dotnet run --project src/CofRules.Cli -- stats
dotnet run --project src/CofRules.Cli -- search "livre de base page 48"
dotnet run --project src/CofRules.Cli -- search "demi-elfe"
```

Variable d’environnement `COF_RULES_DB` (défaut : `data/cof_rules.db`).

## MCP (Cursor)

`.cursor/mcp.json` lance `scripts/run-mcp.sh` (importe la base si elle n’existe pas, puis stdio).

Outils principaux :

| Outil | Rôle |
|---|---|
| `cof_search` | Nom souple **ou** `livre de base page N` |
| `cof_get_page` | Tous les éléments d’une page d’un livre |
| `cof_get_element` | Fiche complète (Markdown + JSON) |
| `cof_get_profile` / `cof_get_people` / `cof_get_voie` / `cof_get_creature` | Fiches typées |
| `cof_stats` / `cof_list_books` / `cof_list_outline` | Catalogue |

## Structure

```
src/CofRules.Core   # SQLite, import JSON, recherche
src/CofRules.Cli    # import / stats / search
src/CofRules.Mcp    # serveur MCP stdio
extract/structured  # lots JSON du livre de base
docs/gm-kits/       # kits MJ texte (INDEX + fiches courtes) pour sessions épargnant les tokens
docs/chronicles/    # journal de suivi (INDEX + etat + chapitres) après compactage de session
```

## Kits MJ

Pour faire jouer un scénario sans relire le PDF : `docs/gm-kits/<scenario>/INDEX.txt`, puis un seul fichier selon le besoin. Compléter avec `cof_*` (1 fiche) si un détail LB manque.

Exemple : `docs/gm-kits/croissez-et-multipliez/`.

- **Jouer** une session : skill `.cursor/skills/cof-gm/SKILL.md` (MJ, secrets, règles MCP, `<rule_application_secret>`).
- **Compacter** l’histoire jouée : skill `.cursor/skills/cof-chronicle/SKILL.md` (INDEX + chapitres sous `docs/chronicles/<slug>/`).
- **Créer** un kit depuis un PDF : skill `.cursor/skills/cof-gm-kit/SKILL.md`.
