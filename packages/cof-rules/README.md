# COF Rules MCP (C#)

Serveur MCP autonome pour le **livre de règles Chroniques Oubliées Fantasy**.
Il n’utilise pas la base SQLite ni les modèles du pipeline d’ingestion Python/Clojure existant.

## Contenu

| Projet | Rôle |
|--------|------|
| `src/CofRules.Core` | Modèle SQLite (EF Core), import JSON, recherche FTS5 |
| `src/CofRules.Cli` | `import`, `stats`, `search`, `dump-pages` |
| `src/CofRules.Mcp` | Serveur MCP stdio `cof-rules` |
| `extract/structured/` | Lots JSON extraits du PDF par sections du sommaire |

## Prérequis

.NET 8 SDK (`dotnet --version`). Sur une VM cloud : `bash /tmp/dotnet-install.sh --channel 8.0` ou le script `dotnet-install.sh` officiel.

PDF source (non versionné, dossier `data/` ignoré par git) :

```bash
uv run gdown "https://drive.google.com/uc?id=1i-InIXfXaERlJHeZRD8b5UpRcmXmnkra" \
  -O data/pdfs/COF_Livre_Regles.pdf
```

## Importer et interroger

```bash
export PATH="$HOME/.dotnet:$PATH"
cd packages/cof-rules
dotnet test
dotnet run --project src/CofRules.Cli -- import --db ../../data/cof_rules.db
dotnet run --project src/CofRules.Cli -- stats
dotnet run --project src/CofRules.Cli -- search "demi-elfe"
```

## MCP Cursor

Entrée dans `.cursor/mcp.json` : serveur `cof-rules` (stdio via `scripts/run-mcp.sh`).

Outils : `cof_stats`, `cof_list_outline`, `cof_search`, `cof_list_elements`, `cof_get_element`,
`cof_list_peoples`, `cof_get_people`, `cof_list_profiles`, `cof_get_profile`, `cof_list_voies`,
`cof_get_voie`, `cof_list_creatures`, `cof_get_creature`, `cof_list_equipment`, `cof_list_magic_items`,
`cof_get_section`, `cof_list_sections`.

Variable d’environnement : `COF_RULES_DB` (défaut `data/cof_rules.db`).
