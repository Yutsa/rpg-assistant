# Plan : pipeline d'ingestion full en Clojure

## Objectif

Remplacer entièrement la pipeline Python d'ingestion raw (`rpg-ingest`, provider PyMuPDF) par une pipeline **100 % Clojure** (PDFBox). L'API et le MCP seront réécrits en Clojure plus tard ; ce plan couvre uniquement l'ingestion jusqu'à la persistance SQLite.

**Hors scope immédiat** : comparateur PyMuPDF/PDFBox (`extractor-compare`), couche sémantique, stat blocks COF2 (phase ultérieure), API HTTP, MCP.

## Modèle de données retenu

| Couche | Rôle | Règle |
|--------|------|-------|
| **Blocs** | Extraction layout (texte + bbox + metadata typo) | Produits par `extract/page.clj` |
| **Sections** | Structure hiérarchique du document | Blocs-titres ; pas de chunk |
| **Chunks** | Unité de contenu exposée (future API/MCP) | **Au plus 1 bloc = 1 chunk** ; pas de fusion multi-blocs |

Enrichissement sémantique ultérieur : `section_id`, `chunk_type`, metadata (texte MJ, texte à lire aux joueurs, etc.).

Le schéma SQLite existant (`campaigns`, `documents`, `ingestion_runs`, `pages`, `page_blocks`, `sections`, `chunks`) est **conservé tel quel** pour compatibilité avec la webapp et les outils actuels.

## État actuel

| Composant | Statut |
|-----------|--------|
| Extraction PDFBox page par page | ✅ `packages/ingest-clj` |
| Blocs (texte, bbox, metadata) | ✅ |
| CLI `extract-page` / `extract-document` / `serve` | ✅ |
| Persistance SQLite depuis Clojure | ✅ phase 0 |
| Sections | ❌ |
| Chunks | ❌ |
| Import `full` sans Python | ❌ (phase 4) |

Aujourd'hui, Clojure est branché uniquement sur le workflow `extractor-compare` via un pont Python (`clojure_pdfbox.py`).

## Architecture cible

```
packages/ingest-clj/src/rpg/
├── ingest/
│   ├── cli.clj                 # commandes (import, extract…)
│   ├── schema.clj              # Malli (existant)
│   ├── extract/                # PDF → blocs
│   │   ├── pdf.clj
│   │   └── page.clj
│   ├── coverage.clj            # rejet PDF scanné
│   ├── reading_order.clj       # heuristiques titres, colonnes, tri spatial
│   ├── sections.clj            # détection titres → arbre de sections
│   ├── chunks.clj              # blocs contenu → chunks 1:1
│   ├── ids.clj                 # doc_*, block_*, sec_*, chunk_*, run_*
│   ├── pipeline.clj            # orchestration import full
│   └── storage/
│       ├── db.clj              # connexion SQLite
│       └── raw.clj             # INSERT campaigns…chunks
```

Plus tard (hors ce plan) : `api/`, `mcp/`, `semantic/`, `stat_blocks/`.

## Phases

### Phase 0 — Fondations

**Dépendances** (`deps.edn`) :
- `com.github.seancorfield/next-jdbc` + `org.xerial/sqlite-jdbc`
- SHA-256 du PDF (`java.security.MessageDigest` ou lib dédiée)

**Modules** :
- `rpg.ingest.ids` — conventions d'IDs alignées sur `packages/core/src/rpg_core/storage/ids.py`
- `rpg.ingest.storage.db` + `storage.raw` — connexion, transactions, `insert-*`, `delete-document-raw-data`, cycle `ingestion_run`

**Hors scope phase 0** : `coverage.clj` (rejet PDF scanné) — reporté / optionnel.

**CLI** :
```bash
clojure -M:ingest import --pdf PATH --campaign-id momie
```
Smoke test : extrait + persiste **pages + blocs** uniquement.

**Critère de done** : lignes visibles en BDD (`data/rpg_assistant.db`) sans appeler Python.

---

### Phase 1 — Normalisation metadata bloc

**Décision** : pas d'exposition de `:column` en metadata (overkill ; la colonne reste dérivée à la volée depuis la bbox en phases 2–3, comme en Python via `column-side` / `is-in-column-band`). Pas de `page-median-font` non plus — à réévaluer en phase 2 si les heuristiques titres en ont besoin.

**Travail** (`page.clj`) :
- Remplacer `:bold?` par `:is-bold` dans les metadata bloc (JSON persisté : `is_bold`, aligné Python).
- Supprimer `:bold?` des metadata exposées.

---

### Phase 2 — Détection de sections

Porter depuis Python (`sections.py`, `reading_order.py`) :

**`reading_order.clj`** :
- Regex : `CHAPTER_RE`, `ALL_CAPS_RE`, `NUMBERED_HEADING_RE`
- Encadrés COF2 : `EN QUELQUES MOTS`, `FICHE TECHNIQUE`, `CRÉDITS`, etc.
- `heading-visual-tier`, `page-median-font`, `column-major-sort-key`
- Garde-fous : titre trop long, drop-cap, en-tête vertical, spread décoratif

**`sections.clj`** :
- `heading-candidate?` — texte + gras + taille police vs médiane page
- `detect-sections` → `{:sections [...] :heading-anchors #{[page idx]} :content-only-section-ids #{...}}`
- Pile hiérarchique (`parent-section-id`, `level`)
- Section fallback `"Document"` si aucun titre
- `refine-section-page-ends` (après chunks)

**Signaux déjà disponibles sur les blocs** : `text`, `bbox`, `max-font-size`, `is-bold`, `line-count`.

**Référence de validation** : tests portés depuis `tests/test_sections.py`, `tests/test_chunking.py` (page 5, 3 sections / 3 chunks).

---

### Phase 3 — Chunks 1:1

**`chunks.clj`** — logique dédiée, **sans** porter `chunking.py` (pas de fusion par budget tokens).

```
1. Construire l'ensemble des heading-anchors
2. Pour chaque bloc (ordre lecture : page → colonne → y0 → x0) :
     si anchor → ignorer (section uniquement)
     sinon → créer un chunk
3. refine-section-page-ends
```

**Assignation bloc → section** :
- Section du dernier anchor **avant** le bloc en ordre de lecture
- Filtrer par **même colonne** (bbox overlap / `column-side`, pas de clé metadata)
- Blocs avant le premier titre → section `"Document"`

**Structure chunk** :
```clojure
{:id (chunk-id document-id page index)
 :section-id ...
 :page-start page :page-end page
 :text (reflow-text block-text)
 :token-count (estimate-tokens text)
 :source-spans [{:page p :page-block-ids [block-id] :bbox ...}]
 :chunk-type-hint nil
 :metadata {}
 :needs-rechunk false}
```

---

### Phase 4 — Pipeline complète

**`pipeline.clj`** — équivalent de `importer.run()` mode `full` :

1. Hash PDF → `document-id`
2. `ensure-campaign`, `create-run` (`status: running`)
3. `extract-document` (PDFBox)
4. Coverage → `rejected` si scan
5. `delete-document-raw-data` si reimport
6. Matérialiser `pages` + `page_blocks`
7. `detect-sections`
8. `build-chunks-1to1`
9. `refine-section-page-ends`
10. `insert-*` en transaction
11. `update-run` (`status: completed`, stats JSON)

**Stats du run** : `page_count`, `block_count`, `section_count`, `chunk_count`, `text_coverage_ratio`, `source_pdf_path`, `extraction_method: "pdfbox"`.

**CLI** :
```bash
clojure -M:ingest import --pdf PATH --campaign-id momie
clojure -M:ingest import --pdf PATH --campaign-id momie --coverage-threshold 0.3 --no-reimport
```

**Critère de done** : import Momie complet sans Python ; `sections` et `chunks` peuplés.

---

### Phase 5 — Qualité COF2

- Porter profil COF2 : `false-heading?` (noms de fiches monstre, etc.)
- `stat_blocks/` (chunks dédiés, metadata structurée) — **second temps**
- Tests régression sur `data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf`
- Heuristiques `chunk_type_hint` optionnelles

---

### Phase 6 — Au-delà (plus tard)

| Composant | Remplace |
|-----------|----------|
| Couche sémantique | `submit_chunk_classifications`, entités, relations |
| API HTTP | `rpg-api` |
| MCP | `rpg-assistant-mcp` |
| Rendu PDF / visual review | `rendering.py`, MCP `prepare_visual_ingestion_review` |

## Ce qu'il ne faut pas porter de Python

- `_group_blocks_for_chunking` / budget ~1200 tokens
- Mode `extractor-compare` / dual lanes (outil dev)
- `raw_layout_json` PyMuPDF (optionnel)
- Merge document-level (`merge_fragmented_blocks`, etc.) — réévaluer seulement si régressions sur blocs Clojure

## Stratégie de tests

1. **Unitaires Clojure** — PDF synthétiques (`test/rpg/ingest/test_fixtures/pdf.clj`)
2. **Intégration BDD** — import → requêtes SQL
3. **Régression COF2** — structure sections + nombre de chunks sur Momie
4. **Python comme oracle temporaire** — comparer sorties pendant le port de `sections.clj` ; retirer une fois tests Clojure suffisants

## Campagne de référence

| Clé | Valeur |
|-----|--------|
| `campaign_id` | `momie` |
| PDF | `data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf` |
| Page piège colonnes | **7** |

## Ordre de travail

```
Phase 0 (storage) → Phase 1 (is-bold) → Phase 2 (sections) → Phase 3 (chunks) → Phase 4 (pipeline) → Phase 5 (COF2)
```

## Références code existant

| Rôle | Chemin Python (spécification) | Chemin Clojure (cible / existant) |
|------|-------------------------------|-----------------------------------|
| Extraction blocs | `packages/ingest/.../layout.py` | `packages/ingest-clj/.../extract/page.clj` |
| Sections | `packages/ingest/.../sections.py` | `packages/ingest-clj/.../sections.clj` |
| Reading order | `packages/ingest/.../reading_order.py` | `packages/ingest-clj/.../reading_order.clj` |
| IDs | `packages/core/.../ids.py` | `packages/ingest-clj/.../ids.clj` |
| Coverage | `packages/ingest/.../coverage.py` | `packages/ingest-clj/.../coverage.clj` |
| Persistance | `packages/core/.../repositories/raw.py` | `packages/ingest-clj/.../storage/raw.clj` |
| Orchestration | `packages/ingest/.../importer.py` | `packages/ingest-clj/.../pipeline.clj` |
| Schéma BDD | `migrations/versions/001_initial_schema.py` | inchangé |

## Comparateur extracteur (contexte)

Le plan [`plan-extractor-compare.md`](plan-extractor-compare.md) reste valide comme **outil de dev** pour affiner `page.clj`. Il n'est pas le chemin de production une fois la pipeline full Clojure en place.
