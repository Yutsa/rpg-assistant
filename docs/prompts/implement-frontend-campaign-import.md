# Prompt — implémenter l'import campagne depuis le frontend

Copier-coller le bloc ci-dessous dans une nouvelle session agent (Cloud Agent ou Cursor local).

---

## Bloc prompt (à copier)

```
Implémente le plan d'import de campagne depuis le frontend décrit dans docs/plan-frontend-campaign-import.md.

## Objectif

Permettre d'uploader un PDF depuis http://127.0.0.1:4200/campaigns, via la pipeline Clojure (clojure -M:ingest import → pipeline/import-pdf!), avec choix explicite du profil de jeu (v1 : CoF 2 uniquement dans le select), progression par polling, et redirection vers le document ingéré.

## Contraintes impératives

- Pipeline d'import UI : **Clojure uniquement** (pas rpg-ingest Python / MCP import_pdf).
- Respecter AGENTS.md : tests via `uv run python -m pytest` (pas `uv run pytest`).
- Minimiser le scope : pas de batch, pas de WebSocket, pas de migration seed-campaigns.sh, pas de MCP.
- Réutiliser les conventions existantes (clojure_pdfbox.py, routers API, signals Angular, MatDialog, data-testid).
- Profil jeu : choix **obligatoire** en UI ; passer `--game-system cof2` au CLI Clojure ; catalogue via GET /ingestion/game-systems (pas de liste hardcodée dans Angular).
- Import long (1–2 min) : POST /imports retourne 202 immédiatement ; background task + polling GET /ingestion-runs/{id}.
- Ne pas modifier la pipeline Clojure elle-même sauf bug bloquant avéré.

## Ordre d'implémentation (suivre strictement)

### Étape 1 — Wrapper Python

Créer packages/ingest/src/rpg_ingest/raw/clojure_import.py :
- run_clojure_import(pdf_path, campaign_id, campaign_title="", game_system="cof2", db_path=None, coverage_threshold=0.3, reimport=True, timeout_s=600) → dataclass ClojureImportResult
- Subprocess : clojure -M:ingest import --pdf … --campaign-id … --game-system … [--db …] [--no-reimport si reimport=false]
- Factoriser si pertinent _clojure_subprocess_env / _INGEST_CLJ_DIR depuis clojure_pdfbox.py (module commun clojure_runtime.py ou similaire)
- Parser stdout JSON (snake_case, aligné packages/ingest-clj/src/rpg/ingest/cli.clj import-command)
- Lever une exception claire si status in {failed, rejected} ou subprocess en erreur

Tests : tests/test_clojure_import.py (PDF synthétique pymupdf avec couverture suffisante ; skip si clojure/java absent).

### Étape 2 — API REST

Nouveau router packages/api/src/rpg_api/routers/imports.py :

| Endpoint | Comportement |
|----------|--------------|
| GET /ingestion/game-systems | Catalogue profils (source : rpg_ingest.raw.stat_blocks.registry) ; v1 exposer cof2 avec label « Chroniques Oubliées Fantasy 2 », default=true |
| POST /imports | multipart : file, campaign_id, campaign_title?, game_system (défaut cof2), reimport? ; valider MIME/taille/campaign_id regex/game_system connu ; sauver dans data/uploads/ ; lancer run_clojure_import en background ; retourner 202 + ingestion_run_id |
| GET /ingestion-runs/{id} | Miroir MCP get_ingestion_status → IngestionRunOut |

Schémas dans schemas.py : GameSystemOut, ImportCreateOut, IngestionRunOut.
Enregistrer le router dans main.py.
Variables env : RPG_UPLOAD_DIR, RPG_MAX_UPLOAD_MB, RPG_IMPORT_TIMEOUT_S (valeurs par défaut raisonnables).
S'assurer que stats.source_pdf_path pointe vers le fichier uploadé (chemin absolu passé au CLI).

Tests : tests/test_api_imports.py (mock run_clojure_import pour POST + poll GET ; 422 game_system inconnu ; validation fichier).

### Étape 3 — Frontend Angular

Service campaign-api.service.ts :
- listGameSystems(), importPdf(formData), getIngestionRun(runId)

Modèles campaign.models.ts : GameSystem, ImportCreateResponse, IngestionRun.

Dialog apps/web/src/app/features/campaigns/dialogs/import-campaign-dialog/ :
- Champs : fichier PDF, campaign_id (slug auto depuis filename), campaign_title optionnel, mat-select profil (GET /ingestion/game-systems, défaut cof2), checkbox reimport
- États : formulaire → upload/spinner → poll toutes les 2s → succès (navigate /documents/{documentId}, mention stat_block_profile + stat_block_count) ou erreur

Brancher sur campaign-list.page : bouton « Importer un PDF » + CTA sur empty state.

Patterns : pdf-viewer-dialog (MatDialog), signals, data-testid (import-campaign-dialog, import-submit, …).

### Étape 4 — Vérification finale (obligatoire AGENTS.md)

1. uv run python -m pytest tests/test_clojure_import.py tests/test_api_imports.py -q
2. bash .cursor/scripts/dev-stack.sh restart && bash .cursor/scripts/dev-stack.sh status
3. Test manuel ou e2e : upload d'un PDF COF2 (ex. data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf) profil CoF 2
4. Vérifier stats : extraction_method=pdfbox, stat_block_profile=cof2
5. Capture preuve : dialog + page document post-import (capture-verification.sh ou Playwright)

## Critères d'acceptation (tous requis)

- [ ] Upload PDF depuis /campaigns avec profil CoF 2 explicite
- [ ] Import via clojure -M:ingest import (stats.extraction_method = pdfbox)
- [ ] GET /ingestion/game-systems alimente le mat-select
- [ ] Polling jusqu'à status terminal ; messages clairs si rejected/failed
- [ ] Redirection /documents/{document_id} ; fiches/sections/chunks lisibles
- [ ] Tests automatisés wrapper + API
- [ ] Preuve visuelle fournie

## Fichiers de référence

- Plan : docs/plan-frontend-campaign-import.md
- CLI Clojure : packages/ingest-clj/src/rpg/ingest/cli.clj, pipeline.clj
- Bridge existant : packages/ingest/src/rpg_ingest/raw/clojure_pdfbox.py
- Registre profils : packages/ingest/src/rpg_ingest/raw/stat_blocks/registry.py
- MCP statut (à miroir) : packages/mcp/src/rpg_mcp/server.py get_ingestion_status
- Frontend campagnes : apps/web/src/app/features/campaigns/
- Script réimport dev : .cursor/scripts/clojure-import-momie.sh

## Git

- Branche : cursor/frontend-campaign-import-433b (ou suffixe agent approprié)
- PR draft avec captures dans le body
- Commits atomiques par étape (wrapper → API → frontend → tests)
```

---

## Variante courte (si contexte limité)

```
Implémente docs/plan-frontend-campaign-import.md en 4 étapes : (1) clojure_import.py + tests, (2) API POST /imports + GET /ingestion/game-systems + GET /ingestion-runs/{id}, (3) dialog import Angular sur /campaigns avec select profil CoF2, (4) tests + stack dev + capture preuve. Pipeline Clojure uniquement. Suivre AGENTS.md.
```
