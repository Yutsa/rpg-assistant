# RPG Assistant — guide pour les agents Cursor

Ce dépôt ingère des PDF d'aventures RPG en deux couches : **raw** (déterministe) puis **semantic** (soumise par agent via MCP).

## Structure du monorepo

| Dossier | Package | Rôle |
|---------|---------|------|
| `packages/core` | `rpg-core` | Modèles Pydantic, couche storage, utilitaires fiches |
| `packages/ingest` | `rpg-ingest` | Pipeline PDF + CLI `rpg-ingest` |
| `packages/mcp` | `rpg-mcp` | Serveur MCP `rpg-assistant-mcp` |
| `packages/api` | `rpg-api` | API REST FastAPI |
| `apps/web` | — | Frontend Angular |

Workspace `uv` à la racine : `uv sync` installe tous les packages en mode editable.

## Lancer l'application (dev local)

### Commande unique (agents — à utiliser en priorité)

Quand l'utilisateur demande de **lancer l'appli** ou de **voir les campagnes** :

```bash
bash .cursor/scripts/launch-app.sh
```

Ce script (idempotent) :
1. importe les 5 PDF COF2 si la base est vide (`seed-campaigns.sh`, `--skip-compare-lanes`) ;
2. démarre API + Angular via `dev-stack.sh restart` ;
3. affiche le lien **http://127.0.0.1:4200/**.

**Ne pas** réimporter manuellement les PDF ni lancer `npm start` à la main — le bootstrap cloud et `launch-app.sh` couvrent déjà Node, `npm install`, analytics et ports.

Attendre la fin du script d'install Cursor (`.cursor/environment.json`) si `node_modules` ou les campagnes manquent encore.

### Démarrage manuel (développeurs)

Après `uv sync`, `.env` et `uv run alembic upgrade head` :

1. **API** — `uv run rpg-api` → [http://127.0.0.1:8000](http://127.0.0.1:8000) (docs : `/docs`)
2. **Frontend** — `cd apps/web && npm install && npm start` → [http://localhost:4200](http://localhost:4200)

Node.js **22.22.3+** requis (`apps/web/.nvmrc`). Sur les VMs cloud, `/exec-daemon/node` (v22.14) est trop ancien : prioriser le binaire nvm (`PATH="$HOME/.nvm/versions/node/v22.22.3/bin:$PATH"`).

### Scripts utilitaires

```bash
bash .cursor/scripts/launch-app.sh          # campagnes + stack (recommandé agents)
bash .cursor/scripts/dev-stack.sh restart   # stack seule (ports 8000/4200)
bash .cursor/scripts/dev-stack.sh status
bash .cursor/scripts/dev-stack.sh stop
bash .cursor/scripts/seed-campaigns.sh      # import COF2 si DB vide
```

`dev-stack.sh` : tmux `rpg-api-server` / `rpg-web-server`, libère les ports, `NG_CLI_ANALYTICS=false`, attend `/health` et le frontend avant de rendre la main.

## Clôture de tâche — vérification manuelle obligatoire

À la fin de **toute tâche** qui modifie l'ingestion, l'API, le frontend ou les données en base, l'agent doit **préparer l'environnement** pour que l'utilisateur puisse valider visuellement, et **fournir une preuve** (capture ou vidéo). Ne pas se limiter aux tests automatisés.

### Checklist agent (fin de PR / fin de tâche)

1. **Réimport** si la pipeline ou le chunking a changé :
   ```bash
   bash .cursor/scripts/clojure-import-momie.sh
   # ou import équivalent (Python MCP/CLI) pour la campagne concernée
   ```
   Noter le `document_id` retourné (JSON du CLI ou MCP).

2. **Stack dev prête** :
   ```bash
   bash .cursor/scripts/dev-stack.sh restart
   bash .cursor/scripts/dev-stack.sh status   # API=200, Web=200
   ```

3. **Preuve visuelle** — au moins une des options :
   - **Capture écran UI** (prioritaire si la tâche touche blocs/chunks/pages) :
   ```bash
   cd apps/web
   node ../../.cursor/scripts/capture-pdf-viewer.mjs DOCUMENT_ID PAGE ../../artifacts/verification-page-PAGE.png
   ```
     Inclure la capture dans le résumé / la PR (`/opt/cursor/artifacts/` sur Cloud Agent).
   - **Vidéo courte** Playwright si interaction multi-étapes (`npx playwright test … --video=on`).
   - **Rendu MCP** en secours : `prepare_visual_ingestion_review(document_id, seed=42)` + lecture des PNG.

4. **Indiquer à l'utilisateur** comment reproduire :
   - URL directe : `http://127.0.0.1:4200/documents/{document_id}` → bouton « Visualisation PDF » → page concernée ;
   - ce qui a changé et ce qu'il doit contrôler (ex. « page 5 : 1 chunk titre, 1 chunk corps fiche technique »).

### Campagne de référence pour vérif ingestion

| Élément | Valeur |
|---------|--------|
| PDF | `data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf` |
| `campaign_id` | `momie` |
| Page de contrôle typique | **5** (titre spread + fiche technique) |
| Import Clojure | `bash .cursor/scripts/clojure-import-momie.sh` |

Le `document_id` change à chaque réimport (hash du PDF) ; toujours utiliser celui du **dernier run** (`ingestion_run_id` / JSON CLI), pas une valeur figée dans ce guide.

## Serveur MCP `rpg-assistant`

Utilise **toujours** le serveur MCP `rpg-assistant` pour consulter ou enrichir les données ingérées. Ne réimplémente pas l'ingestion ni n'interroge la base à la main sauf pour du debug explicite demandé par l'utilisateur.

Base SQLite par défaut : `data/rpg_assistant.db` (créée après `uv run alembic upgrade head`).

## Explorer les données extraites (lecture)

Quand l'utilisateur veut voir ce qui a été ingéré :

1. Identifier le `document_id` (résultat de `import_pdf` / CLI, ou dernier run de la campagne).
2. `list_sections(document_id)` — structure du document (titres, pages).
3. `list_chunks(document_id, section_id=..., limit=...)` — aperçus des morceaux.
4. `get_chunk(chunk_id)` — texte complet, spans source, métadonnées.
5. `list_stat_blocks(document_id)` — index léger des fiches monstre/PNJ (name, nc, chunk_id, pages).
6. `get_stat_block(document_id, name)` — fiche structurée + `source_refs` ; recherche insensible à la casse et aux accents sur `name` ou `subtitle`.
7. `get_source_excerpt(page_block_ids)` — vérifier le texte source PDF (bbox).

Pour le statut d'un import : `get_ingestion_status(ingestion_run_id)`.

## Vérification visuelle (boucle de feedback)

Pour comparer le rendu visuel du PDF avec les sections et chunks extraits :

1. `prepare_visual_ingestion_review(document_id, seed=42)` — échantillonne des sections/chunks aléatoires et rend les pages PDF correspondantes en PNG. Le chemin source est résolu depuis le dernier import (`source_pdf_path` dans les stats du run) ; passer `pdf_path` si besoin.
2. Lire chaque `image_path` retourné (outil Read — vision).
3. Comparer avec les sections/chunks du JSON retourné.
4. Produire un rapport structuré (`section_id`, `chunk_id`, `issue`, sévérité). Checklist : ressource `ingestion://prompts/visual_ingestion_review`.

Réponds en français si l'utilisateur parle français. Cite des extraits courts et indique `chunk_id` / pages pour que l'utilisateur puisse retrouver la source.

## Tester le MVP sémantique (écriture)

Workflow d'enrichissement :

1. `list_chunks` → lire quelques chunks représentatifs avec `get_chunk`.
2. `submit_chunk_classifications` — types autorisés via ressource `ingestion://schemas/chunk_classification`.
3. `submit_entities` — **obligatoire** : chaque entité a des `source_refs` pointant vers de vrais `chunk_id`.
4. `validate_semantic_layer(campaign_id)` — corriger les erreurs et resoumettre.
5. `submit_relations` puis `get_semantic_summary(campaign_id)`.

Schémas et prompt de référence : ressources MCP `ingestion://schemas/*` et `ingestion://prompts/entity_extraction`.

## Import PDF

- Petit test / une campagne : MCP `import_pdf`.
- Gros PDF ou batch : CLI `uv run rpg-ingest raw extract <pdf> --campaign-id <id>`.
- Pour les scénarios **Chroniques Oubliées Fantasy 2**, passer `game_system=cof2` à l'import (détection et parsing des fiches monstre/PNJ ; chunks `stat_block` avec métadonnées structurées dans `ChunkRecord.metadata`).

Demande confirmation avant `import_pdf` ou toute soumission sémantique si l'utilisateur n'a pas explicitement demandé d'écrire en base.

## Ingestion Clojure (pipeline full PDFBox)

Remplacement progressif de la pipeline Python raw par `packages/ingest-clj`. **Plan et suivi d'avancement** : [`docs/plan-clojure-ingestion-full.md`](docs/plan-clojure-ingestion-full.md) — section **« Suivi d'avancement (pour les agents) »** en tête de fichier.

Quand l'utilisateur dit **« continue l'implémentation de la prochaine phase du plan »** (ou variante) :

1. Lire la section suivi du plan → identifier la phase marquée **PROCHAINE**.
2. Implémenter uniquement cette phase (sous-tâches et critères de done listés).
3. Tests : `cd packages/ingest-clj && clojure -M:test`.
4. Mettre à jour le suivi d'avancement en fin de PR (cocher la phase, pointer la suivante).

**État au 2026-06-27** : phases 0–4 livrées ; **prochaine = phase 5** (fiches monstre : profils jeu Malli + multimethodes, `stat_blocks/`, profil `:cof2`).

## Campagne de référence (dev)

- `campaign_id` : `momie`
- PDF : `data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf`
- `document_id` : **variable** — hash stable du PDF (`doc_*` retourné par le dernier import) ; ne pas hardcoder une valeur obsolète.
- Dernier run réussi : vérifier avec `get_ingestion_status` ou le JSON de `clojure-import-momie.sh`.

## Cursor Cloud specific instructions

Projet Python géré par `uv` (voir `readme.md` pour install/CLI/MCP/API). Quatre surfaces : **CLI** `rpg-ingest`, **serveur MCP** `rpg-assistant-mcp` (stdio), **API HTTP** `rpg-api` (FastAPI), et **frontend Angular** `apps/web` (voir [Lancer l'application](#lancer-lapplication-dev-local)).

### Setup automatique (`.cursor/environment.json`)

Au démarrage, Cursor exécute `uv sync` puis `.cursor/scripts/cloud-agent-install.sh` :

- **Clojure CLI** (`clojure`, `clj`) — installé par le script si absent (Java 21 déjà présent sur la VM).
- **Clojure MCP** ([`io.github.bhauman/clojure-mcp`](https://github.com/bhauman/clojure-mcp)) — installé globalement (`clojure -Ttools install-latest`) ; serveur MCP `clojure-mcp` dans `.cursor/mcp.json` (profil `:cli-assist` pour Cursor).
- **Node.js 22.22.3** (via nvm, version `apps/web/.nvmrc`) + **`npm install`** dans `apps/web` — évite le téléchargement Node et les dépendances au premier `dev-stack.sh`.
- **Playwright Chromium** — pré-installé (`npx playwright install chromium`) pour les captures d'écran de preuve sans téléchargement (~115 Mo).
- **`lsof`** — installé si absent (libération des ports 8000/4200).
- **`NG_CLI_ANALYTICS=false`** — écrit dans `.env` et `.cursor/cache/frontend-toolchain.env` (pas de prompt bloquant `ng serve`).
- **5 PDF COF2** — téléchargés dans `data/pdfs/` via `gdown` (Google Drive) s'ils ne sont pas déjà présents :
  - `COF2_10_Mondanites_Et_Momies_web_v1a.pdf`
  - `COF2_07_Le_Dernier_Faelys_web_v0.pdf`
  - `COF2_Mortelle_Xelys.pdf`
  - `COF2_Croissez_Et_Multipliez.pdf`
  - `COF2_Retour_En_Grace.pdf`
- **`.env`** — créé depuis `.env.example` avec `RPG_PDF_MOMIE` et `RPG_PDF_FAELYS` pointant vers les PDF locaux.
- **Base SQLite** — `uv run alembic upgrade head` crée `data/rpg_assistant.db`.
- **Campagnes COF2** — `seed-campaigns.sh` importe les 5 PDF si la table `campaigns` est vide (~1–2 min au bootstrap, pas au lancement).

Aucune action manuelle requise pour Clojure, les PDF ou les campagnes sur une VM cloud agent à jour.

### Commandes utiles

- **Application** : `bash .cursor/scripts/launch-app.sh` — voir [Lancer l'application](#lancer-lapplication-dev-local).
- **Réimport Momie (Clojure)** : `bash .cursor/scripts/clojure-import-momie.sh`
- **Capture preuve UI** : `bash .cursor/scripts/capture-verification.sh DOCUMENT_ID PAGE` (stack dev requise)
- **Tests** : lancer `uv run python -m pytest`, **pas** `uv run pytest`. `tests/test_visual_review.py` fait `from tests.test_campaign_discovery import ...`, ce qui exige la racine du repo sur `sys.path` ; seul `python -m pytest` (qui ajoute le CWD) le fournit. Avec `pytest` direct la collecte échoue (`ModuleNotFoundError: No module named 'tests'`).
- **Benchmarks PDF réels** : attentes statiques dans `tests/fixtures/real_pdf_benchmark.py` (pages pièges audit COF2). Lancer `uv run python -m pytest tests/test_real_pdf_benchmark.py -m real_pdf -q` — les PDF sont dans `data/pdfs/` après le bootstrap cloud.
- **Tests campagnes supplémentaires** : `tests/test_cof2_audit_extra_campaigns.py` utilise aussi les PDF dans `data/pdfs/`.
- **Test ignoré** : les benchmarks `real_pdf` sont `skipped` si les PDF COF2 ne sont pas disponibles localement (hors cloud agent). Les tests synthétiques génèrent leurs PDF à la volée via `pymupdf`.
- **Aucun linter configuré** (pas de ruff/flake8/black/mypy ni de hooks pre-commit/husky).
- **Ingestion** : `import_pdf` / `rpg-ingest raw extract` rejette un PDF si `text_coverage_ratio < 0.3` (heuristique ≈ `len(texte)*50 / aire_page`, voir `packages/ingest/src/rpg_ingest/raw/coverage.py`). Pour un PDF de test synthétique, viser ≳ 2900 caractères par page A4, sinon utiliser `--coverage-threshold 0.0`.
