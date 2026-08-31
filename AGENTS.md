# COF Rules — guide agents

Ce dépôt expose **uniquement** un serveur MCP pour les références Chroniques Oubliées Fantasy 2, plus des **kits MJ** texte pour faire jouer des scénarios sans relire les PDF.

## Stack

- .NET 10 (`CofRules.slnx`)
- SQLite + FTS5 (`data/cof_rules.db`)
- Extraots source : `extract/structured/*.json` (livre de base)
- Kits MJ : `docs/gm-kits/<scenario>/` (fichiers `.txt` courts + `INDEX.txt`)
- Chroniques : `docs/chronicles/<slug>/` (INDEX + etat + chapitres ; `mj.txt` = secrets)
- Table mixte : fiche `docs/pc-sheets/`, mémoire PJ `docs/pc-memory/`, fil public `docs/table/<slug>-public.txt`

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

Suivre le skill **`.cursor/skills/cof-gm/SKILL.md`** (rôle MJ, secrets, recadrage doux, encadré `<rule_application_secret>`).

1. Ouvrir **seulement** `docs/gm-kits/<scenario>/INDEX.txt`.
2. Charger **un** fichier du kit selon le besoin (pitch, déroulé, fiches, règles, fins).
3. Pour un détail absent du kit : **un** appel MCP (`cof_search` / `cof_get_creature` / `cof_get_element`), pas le livre entier.
4. Jets / PNJ mécaniques : dés réels + encadré secret ; hors balise, seule l’interprétation fictionnelle.

Kit actuel : `docs/gm-kits/croissez-et-multipliez/` (scénario *Croissez et multipliez*).

### Compagnons IA (table solo)

Skill **`.cursor/skills/cof-pj/SKILL.md`**. Défaut : **1 agent PJ** pour tous les compagnons (retrait, combat + spécialités). Fil MJ séparé. Le MJ écrit `docs/table/<slug>-public.txt` (1–3 beats, fiction seulement) ; chaque PJ tient `docs/pc-memory/<nom>.txt`. Pas de kit MJ, pas de bestiaire MCP, pas de transcript. Split 1 subagent / PJ seulement si voix mélangées / secrets inter-PJ / campagne longue (`resume` du même fil).

### Chronique (contexte trop gros)

Skill **`.cursor/skills/cof-chronicle/SKILL.md`**. Déclenchement **manuel** (compacter / archiver la session). Produit `docs/chronicles/<slug>/INDEX.txt` (résumé très court + pointeurs) et des chapitres. Reprise : INDEX + `etat.txt`, un fichier détail si trou. Pas le transcript. Agents PJ : ne pas ouvrir ce dossier.

### Créer un nouveau kit depuis un PDF

Suivre le skill **`.cursor/skills/cof-gm-kit/SKILL.md`** (approche hybride texte + vision ciblée + MCP règles).
