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
5. `get_source_excerpt(page_block_ids)` — vérifier le texte source PDF (bbox).

Pour le statut d'un import : `get_ingestion_status(ingestion_run_id)`.

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

Demande confirmation avant `import_pdf` ou toute soumission sémantique si l'utilisateur n'a pas explicitement demandé d'écrire en base.

## Campagne de référence (dev)

- `campaign_id` : `momie`
- `document_id` : `doc_010672301b36` (Mondanités et Momie, 20 pages, 75 chunks)
- Dernier run réussi : vérifier avec `get_ingestion_status` si besoin.
