# COF Rules — guide agents

Ce dépôt expose **uniquement** un serveur MCP pour les références Chroniques Oubliées Fantasy 2.

## Stack

- .NET 10 (`CofRules.slnx`)
- SQLite + FTS5 (`data/cof_rules.db`)
- Extraots source : `extract/structured/*.json` (livre de base)

## Commandes

```bash
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$DOTNET_ROOT:$PATH"
dotnet test
dotnet run --project src/CofRules.Cli -- import
```

MCP : `bash scripts/run-mcp.sh` (stdio). Outils `cof_*` — voir `.cursor/rules/cof-rules-mcp.mdc`.

Ne pas réintroduire l’ancien pipeline Python / Angular / Clojure d’ingestion de campagnes.
