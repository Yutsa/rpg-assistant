# COF Rules — guide agents

Ce dépôt expose **uniquement** un serveur MCP pour les références Chroniques Oubliées Fantasy 2, plus des **kits MJ** texte pour faire jouer des scénarios sans relire les PDF.

## Stack

- .NET 10 (`CofRules.slnx`)
- SQLite + FTS5 (`data/cof_rules.db`)
- Extraots source : `extract/structured/*.json` (livre de base)
- Kits MJ : `docs/gm-kits/<scenario>/` (fichiers `.txt` courts + `INDEX.txt`)

## Commandes

```bash
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$DOTNET_ROOT:$PATH"
dotnet test
dotnet run --project src/CofRules.Cli -- import
dotnet run --project src/CofRules.Cli -- search "ogre"
dotnet run --project src/CofRules.Cli -- search "livre de base page 208"
```

MCP : `bash scripts/run-mcp.sh` (stdio). Outils `cof_*` — voir `.cursor/rules/cof-rules-mcp.mdc`.

Ne pas réintroduire l’ancien pipeline Python / Angular / Clojure d’ingestion de campagnes.

## Faire jouer un scénario (économe en tokens)

1. Ouvrir **seulement** `docs/gm-kits/<scenario>/INDEX.txt`.
2. Charger **un** fichier du kit selon le besoin (pitch, déroulé, fiches, règles, fins).
3. Pour un détail absent du kit : **un** appel MCP (`cof_search` / `cof_get_creature` / `cof_get_element`), pas le livre entier.

Kit actuel : `docs/gm-kits/croissez-et-multipliez/` (scénario *Croissez et multipliez*).
