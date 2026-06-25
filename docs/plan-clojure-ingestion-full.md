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
| Metadata `:is-bold` alignée Python | ✅ phase 1 |
| CLI `extract-page` / `extract-document` / `serve` | ✅ |
| Persistance SQLite depuis Clojure | ✅ phase 0 |
| Sections | 🔲 phase 2 (en cours) |
| Chunks | ❌ phase 3 |
| Import `full` sans Python | ❌ phase 4 |

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

### Phase 1 — Normalisation metadata bloc ✅

**Décision** : pas d'exposition de `:column` en metadata (overkill ; la colonne reste dérivée à la volée depuis la bbox en phases 2–3, comme en Python via `column-side` / `is-in-column-band`). `page-median-font` calculé à la volée en phase 2 depuis les blocs de la page (pas stocké en metadata).

**Livré** (`page.clj`, PR #37) :
- `:is-bold` dans les metadata bloc (JSON persisté : `is_bold`, aligné Python).
- `:bold?` supprimé des metadata exposées.

---

### Phase 2 — Détection de sections

**Prérequis** : phase 1 livrée (`:is-bold` dans les metadata bloc, aligné `is_bold` Python).

**Objectif** : à partir des pages extraites (liste de blocs ordonnés par `block-index`), produire un arbre de `SectionRecord` + les ancres titre consommées par la phase 3 (chunks). **Pas de persistance BDD** en phase 2 — uniquement modules Clojure + tests unitaires.

**Hors scope phase 2** :
- `StatBlockProfile` / `false-heading?` COF2 → phase 5
- `refine-section-page-ends` : **implémenté ici**, mais **appelé** seulement en phase 3/4 (nécessite les chunks)
- `insert-sections!` → phase 4

#### 2.1 — Contrat d'entrée / sortie

**Entrée** — pages extraites par `extract/pdf.clj`, chaque page :

```clojure
{:page-number 5
 :width 510.0 :height 650.0
 :blocks [{:block-index 0 :text "..." :bbox {:x0 .. :y0 .. :x1 .. :y1 ..}
            :metadata {:max-font-size 13.0 :is-bold true :line-count 1 ...}} ...]}
```

**Sortie** — `detect-sections` :

```clojure
{:sections [{:id "sec_..." :campaign-id ... :document-id ...
             :parent-section-id nil|:sec_... :title "..." :level 1-4
             :page-start 5 :page-end 7}]
 :heading-anchors [[page-number block-index] ...]   ; ordre lecture spatial
 :content-only-section-ids #{"sec_..."}}          ; préambules « Introduction »
```

Alignement strict sur `SectionDetectionResult` Python et schéma SQLite `sections` (`parent_section_id`, `level`, `page_start`, `page_end`).

#### 2.2 — Fichiers à créer

| Fichier | Rôle |
|---------|------|
| `reading_order.clj` | Géométrie colonnes, tri spatial, heuristiques texte/titre |
| `sections.clj` | Candidats titre, hiérarchie, préambules, `detect-sections` |
| `test/rpg/ingest/reading_order_test.clj` | Tests unitaires géométrie + regex |
| `test/rpg/ingest/sections_test.clj` | Tests portés depuis Python |
| `test/rpg/ingest/test_fixtures/layout.clj` | Helpers `make-block`, `make-page` (miroir `tests/fixtures/layout.py`) |

Ajout mineur dans `ids.clj` : `(defn section-id [] (new-id "sec"))` — ou appel direct `(new-id "sec")`.

#### 2.3 — `reading_order.clj` (port fidèle)

Constantes à reporter telles quelles depuis `reading_order.py` :

| Constante | Valeur | Usage |
|-----------|--------|-------|
| `SPATIAL_Y_TOLERANCE` | 5.0 | Bucket Y pour tri spatial |
| `MIN_COLUMN_OVERLAP` | 0.35 | `is-in-column-band?` |
| `NARROW_BOX_MAX_WIDTH` | 160.0 | Encadrés étroits |
| `NARROW_BOX_X_MARGIN` | 35.0 | Zone contenu sous encadré |
| `NARROW_BOX_MAX_VERTICAL_GAP` | 130.0 | Gap vertical encadré → corps |
| `DECORATIVE_FONT_RATIO` | 2.0 | Titre spread décoratif |
| `DECORATIVE_MIN_FONT` | 28.0 | idem |
| `DECORATIVE_TOP_RATIO` | 0.33 | Titre dans le tiers haut |
| `VERTICAL_HEADER_MAX_WIDTH` | 20.0 | En-tête vertical marge |
| `VERTICAL_HEADER_MIN_X_RATIO` | 0.85 | idem |
| `TITLE_CASE_MAX_WORDS` | 6 | Titre casse mixte |
| `TITLE_CASE_MIN_WORDS` | 2 | idem |
| `MAX_SUBORDINATE_CHAPTER_PAGE_GAP` | 3 | Sous-titres rattachés au chapitre |
| `PAGE_BANNER_PREFIXES` | INTRODUCTION, IMPLICATION, CONCLUSION | Bannières pleine page |

**Regex** (clojure.core `re-pattern`, flags `(?i)` / `(?u)` selon besoin) :

- `CHAPTER_RE` — `^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b`
- `ALL_CAPS_RE` — majuscules + accents français (`ÀÂÄ…`)
- `NUMBERED_HEADING_RE` — `^(\d+(?:\.\d+)*)\s+(.+)$` (utilisé en phase 3 aussi ; définir ici)
- `TITLE_CASE_WORD_RE`, `PAGE_NUMBER_LABEL_RE`, `LIST_ITEM_MARKER_RE`, `LIST_ITEM_NAME_RE`
- `CONDITIONAL_HOOK_RE` — `^Si\s+` (hooks Faelys)

**Fonctions publiques** (ordre d'implémentation suggéré) :

1. **Géométrie** — `horizontal-overlap-ratio`, `column-side`, `is-in-column-band?`, `is-same-y-band?`, `spatial-sort-key`, `column-major-sort-key`
2. **Typo page** — `page-median-font` (médiane des `:max-font-size` non nuls ; défaut 12.0)
3. **Nettoyage texte** — `strip-glyphs` (catégories Unicode Cf/Co/Cs, comme `_strip_glyphs`)
4. **Classifieurs texte** — `is-chapter-heading?`, `is-all-caps-heading-text?`, `is-meta-box-heading?` (`CRÉDITS`, `EN QUELQUES MOTS`, `FICHE TECHNIQUE`), `is-reward-box-heading?`, `is-title-case-heading?`, `is-conditional-hook-heading?`, `is-list-item-block?`, `is-editorial-credits-block?`
5. **Classifieurs visuels** — `is-decorative-spread-title?`, `is-spread-title-pair?`, `is-vertical-running-header?`, `is-page-banner-heading?`
6. **Agrégation** — `heading-visual-tier` → `"meta"` \| `"banner"` \| `"chapter"` \| `"subordinate"` \| `"other"`
7. **Utilitaires** — `normalize-section-title`, `find-block`, `spatially-sorted-headings`, `page-is-sparse?`, `page-is-decorative-only?`

**Décision colonnes** (rappel phase 1) : pas de clé `:column` en metadata ; toujours dériver via `column-side` / `is-in-column-band?` depuis la bbox.

#### 2.4 — `sections.clj` (algorithme)

**Constantes locales** :

| Constante | Valeur |
|-----------|--------|
| `MIN_BOLD_HEADING_LEN` | 3 |
| `PREAMBLE_TITLE` | `"Introduction"` |
| `CAPS_SUBORDINATE_MAX_GAP` | 80.0 |
| `TABLE_ROW_LABEL_RE` | `^[A-Z]-\d+$` (rejeter faux titres tableau) |

**Étape A — Scanner les candidats titre** (`heading-candidate?`)

Pour chaque bloc de chaque page, calculer `median = page-median-font(blocks)` puis rejeter si :

| Garde-fou | Condition |
|-----------|-----------|
| Texte vide / trop long | `> 120` car., `> 14` mots |
| Drop-cap | 1 lettre majuscule + bloc suivant commence en minuscule |
| En-tête vertical | `is-vertical-running-header?` |
| Spread décoratif | `is-decorative-spread-title?` ou paire avec bloc précédent |
| Ligne tableau | `TABLE_ROW_LABEL_RE` |
| Nom arbre généalogique | `_is_genealogy_diagram_name_heading` (bloc gras court sous « ARBRE GÉNÉALOGIQUE ») |

Accepter si (dans l'ordre, comme Python) :

1. `CHAPTER_RE` match
2. `is-meta-box-heading?` ou `is-reward-box-heading?`
3. `is-title-case-heading?`
4. `NUMBERED_HEADING_RE` + (`is-bold` ou `max-font >= median * 1.05`)
5. `ALL_CAPS_RE` + `len >= 4` + `max-font >= median`
6. `is-bold` + `max-font >= median * 1.15` + longueur 3–80

**Phase 5** ajoutera : `(profile/is-false-heading? block ...)` — stub `profile` nil en phase 2.

**Étape B — Niveau titre** (`heading-level`) :

- `heading-visual-tier` → meta/chapter/banner = 1, subordinate = 2
- `NUMBERED_HEADING_RE` → `min(4, depth + 1)` où depth = nombre de `.` dans le préfixe numérique
- Sinon seuils `max-font` vs médiane : `* 1.3` → 1, `* 1.15` → 2, sinon 3

**Étape C — Tri spatial** : `spatially-sorted-headings` sur la liste `[page block-idx title level]`.

**Étape D — Construction hiérarchique** (boucle sur titres triés) :

```
stack : [{level section-id} ...]
active-chapter-id : sec_... | nil
subordinate-section-ids : #{...}

Pour chaque titre (page, block-idx, title, level) :
  tier = heading-visual-tier(...)
  selon tier :
    meta     → parent nil, level 1
    chapter/banner → vider stack, parent nil, level 1, active-chapter-id = nouveau
    subordinate → parent = chapitre actif si page-gap ≤ 3, ou same-page-caps-parent
    other    → parent = stack (avec same-page-caps-parent si applicable)
  page-end = page du titre suivant, ou dernière page du doc
  pousser SectionRecord + anchor [page block-idx]
  si chapter/banner → reparent-same-page-subordinates!
```

Fonctions auxiliaires à porter :

- `same-page-caps-parent-id` — titre ALL CAPS plus haut, même colonne, gap Y ≤ 80
- `reparent-same-page-subordinates` — sous-titres entre deux chapitres même page restent sous le premier
- `detect-preamble-sections` — bloc corps au-dessus d'un `CHAPTER_RE` même colonne → section `"Introduction"` (`content-only-section-ids`)

**Étape E — Fallback** : aucun titre → une section unique `"Document"` (`page_start`/`page_end` = étendue du doc), `heading-anchors` vide.

**Étape F — Fusion préambules** : insérer sections/anchors préambule **avant** chaque anchor de même page d'ordre inférieur (merge ordonné comme Python L484–509).

**`refine-section-page-ends`** (implémenter, tester isolément) :

```clojure
(defn refine-section-page-ends! [sections chunks]
  ;; Pour chaque section : page-end = max(page-end des chunks assignés)
  ...)
```

#### 2.5 — Ordre d'implémentation (sous-tâches)

| # | Tâche | Critère intermédiaire |
|---|-------|----------------------|
| 2.5.1 | Fixtures `layout.clj` + tests géométrie (`column-side`, overlap) | `clojure -M:test` vert |
| 2.5.2 | Regex + `page-median-font` + classifieurs texte | tests meta box, chapter, title-case |
| 2.5.3 | Garde-fous visuels (spread, vertical header, drop-cap) | test page 5 décoratif Momie |
| 2.5.4 | `detect-sections` squelette + fallback Document | tests chapitres simples |
| 2.5.5 | Pile hiérarchique + subordinates + same-page caps | tests PARTIE I/II, nested |
| 2.5.6 | Préambules Introduction + content-only ids | test page 8 (pas de faux préambule) |
| 2.5.7 | `refine-section-page-ends!` | test unitaire avec chunks mock |

#### 2.6 — Stratégie de tests

**Portage prioritaire** depuis `tests/test_sections.py` :

| Test Python | Comportement attendu |
|-------------|---------------------|
| `test_detect_sections_finds_chapter_headings` | 2 sections chapitre, anchors corrects |
| `test_detect_sections_fallback_when_no_headings` | 1 section `"Document"` |
| `test_detect_sections_rejects_single_character_drop_cap_heading` | `"S"` rejeté |
| `test_detect_sections_keeps_three_character_bold_headings` | `"Fin"` (3 car.) accepté |
| `test_detect_sections_rejects_decorative_spread_title` | `MONDANITÉS` / `ET MOMIE` rejetés ; `EN QUELQUES MOTS` gardé |
| `test_detect_sections_nests_subordinates_under_chapter` | `Les grandes lignes` sous `PARTIE I` |
| `test_detect_sections_finds_title_case_heading` | Title case gras |
| `test_detect_sections_no_false_preamble_when_chapter_in_parallel_column` | pas d'`Introduction` |
| `test_detect_sections_keeps_same_page_subordinates_under_first_chapter` | sous-titre reste sous PARTIE I |
| `test_detect_sections_nests_numbered_heading_under_pre_chapter_title_case` | `1 - Cave` sous `Les abattoirs` |
| `test_detect_sections_rejects_two_character_bold_headings` | `"GM"` → fallback Document |

**Oracle temporaire** (optionnel, sous-tâche 2.5.8) : script ou test d'intégration comparant sortie Clojure vs Python sur les mêmes blocs synthétiques ; retirer quand couverture suffisante.

**Pas en phase 2** : tests COF2 réels (`test_cof2_audit_sections.py`) — phase 5 après profil `false-heading?`.

#### 2.7 — Critères de done phase 2

- [ ] `reading_order.clj` et `sections.clj` compilent, namespaces documentés
- [ ] `clojure -M:test` : tous les tests portés de `test_sections.py` passent
- [ ] `detect-sections` retourne des maps compatibles insertion future (`insert-sections!` phase 4)
- [ ] Aucune régression sur tests existants (`extract_test`, `import_test`, `ids_test`)
- [ ] Pipeline phase 0 inchangé (pas encore branché sur `detect-sections`)

#### 2.8 — Pièges connus (Momie / COF2)

| Piège | Page | Mitigation |
|-------|------|------------|
| Spread titre décoratif | 5 | `is-decorative-spread-title?` + paire `ET MOMIE` |
| Deux colonnes indépendantes | 5, 7, 8 | `is-in-column-band?` pour préambules et assignation (phase 3) |
| Encadrés `EN QUELQUES MOTS` | 5 | `is-meta-box-heading?` → tier `meta`, level 1 |
| Hooks `Si les PJ…` | Faelys | `is-conditional-hook-heading?` → subordinate |
| Faux titres 2 car. (`GM`) | divers | `MIN_BOLD_HEADING_LEN = 3` |

**Signaux bloc disponibles** : `text`, `bbox`, `:max-font-size`, `:is-bold`, `:line-count` (pas `:stat-block-role` en phase 2).

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
