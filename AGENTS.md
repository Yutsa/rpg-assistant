# RPG Assistant — guide pour les agents Cursor

Ce dépôt ingère des PDF d'aventures RPG en deux couches : **raw** (déterministe) puis **semantic** (soumise par agent via MCP).

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

## Campagne de référence (dev)

- `campaign_id` : `momie`
- `document_id` : `doc_010672301b36` (Mondanités et Momie, 20 pages, 75 chunks)
- Dernier run réussi : vérifier avec `get_ingestion_status` si besoin.

## Cursor Cloud specific instructions

Projet Python géré par `uv` (voir `readme.md` pour install/CLI/MCP). Pas de service web ni de GUI : deux surfaces seulement, la **CLI** `rpg-ingest` et le **serveur MCP** `rpg-assistant-mcp` (stdio). Le script d'update (`uv sync`) est déjà lancé au démarrage ; il ne crée pas la base ni le `.env`.

- **Setup runtime (à faire une fois par VM, hors update script)** : `cp .env.example .env` puis `uv run alembic upgrade head` pour créer `data/rpg_assistant.db` (SQLite par défaut, aucun Docker requis). Sans ça, CLI/MCP échouent (table manquante).
- **Tests** : lancer `uv run python -m pytest`, **pas** `uv run pytest`. `tests/test_visual_review.py` fait `from tests.test_campaign_discovery import ...`, ce qui exige la racine du repo sur `sys.path` ; seul `python -m pytest` (qui ajoute le CWD) le fournit. Avec `pytest` direct la collecte échoue (`ModuleNotFoundError: No module named 'tests'`).
- **Test ignoré** : `test_mondanites_chunking` est `skipped` car il dépend d'un PDF COF2 propriétaire absent du repo (`/home/edouard/Téléchargements/...`). C'est normal. Les autres tests génèrent leurs PDF à la volée via `pymupdf`.
- **Aucun linter configuré** (pas de ruff/flake8/black/mypy ni de hooks pre-commit/husky).
- **Ingestion** : `import_pdf` / `rpg-ingest raw extract` rejette un PDF si `text_coverage_ratio < 0.3` (heuristique ≈ `len(texte)*50 / aire_page`, voir `ingestion/raw/coverage.py`). Pour un PDF de test synthétique, viser ≳ 2900 caractères par page A4, sinon utiliser `--coverage-threshold 0.0`.
- **Aucun PDF de la campagne de référence `momie` n'est commité** ; la base de dev démarre vide après migration.
