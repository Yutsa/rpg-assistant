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
│   ├── reading_order.clj       # passe 1 : tri colonne-majeur, garde-fous géométrie
│   ├── sections.clj            # passe 2 : flux typo → sections + block-assignments
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

### Phase 2 — Ordre de lecture + sections (deux passes)

**Prérequis** : phase 1 livrée (`:is-bold` dans les metadata bloc).

**Changement de design** (vs portage direct Python) : au lieu de scanner tous les titres puis reconstruire la hiérarchie a posteriori, on adopte un modèle **deux passes** plus simple et aligné avec le chunking 1:1 :

```
Passe 1 — normaliser l'ordre de lecture (ré-indexer les blocs)
Passe 2 — parcourir en flux : détecter titre/corps + affecter chaque bloc à sa section
```

Le signal principal est le **changement de typo** (taille police, gras) entre blocs consécutifs en ordre de lecture — indicateur titre↔corps — complété par des garde-fous COF2 (spread décoratif, drop-cap, encadrés…).

**Hors scope phase 2** : `StatBlockProfile` / `false-heading?` → phase 5 ; `insert-sections!` → phase 4.

#### 2.1 — Passe 1 : ordre de lecture (`reading_order.clj`)

**Objectif** : garantir que `block-index` reflète l'ordre de lecture humain **avant** toute détection de section.

**Ordre retenu pour COF2** — **colonne-majeur** par page (pas un tri global `y0` puis `x0` qui entremêle les colonnes) :

```
page 1 : colonne gauche (haut→bas) → colonne droite (haut→bas)
page 2 : idem
…
```

Clé de tri : `column-major-sort-key` = `(page-number, column-side, y0, x0)` avec `column-side` dérivé du centre x de la bbox vs `page-width / 2`.

**Fonction** :

```clojure
(defn normalize-reading-order
  "Trie les blocs de chaque page en ordre colonne-majeur et réattribue block-index 0..n."
  [pages]
  ...)
```

**Où l'appeler** :
- En fin d'extraction (`page.clj` ou `pipeline.clj` avant persistance) — les IDs `block_*` reflètent alors l'ordre de lecture en base.
- Remplacer le tri final actuel `(y0, x0)` global dans `merge-segments-by-font` par ce tri colonne-majeur.

**Conséquence** : un réimport sera nécessaire pour les documents déjà en BDD phase 0 (index ≠ ordre de lecture). Acceptable — pipeline pas encore en prod.

**Utilitaires à porter** depuis `reading_order.py` (géométrie + garde-fous, pas toute la logique `detect_sections` Python) :

| Groupe | Fonctions |
|--------|-----------|
| Géométrie | `column-side`, `horizontal-overlap-ratio`, `is-in-column-band?`, `column-major-sort-key` |
| Typo page | `page-median-font` |
| Texte | `strip-glyphs`, regex chapitre / caps / numéroté / meta box |
| Rejets visuels | `is-decorative-spread-title?`, `is-vertical-running-header?`, `is-list-item-block?` |
| Titres | `is-meta-box-heading?`, `is-chapter-heading?`, `is-title-case-heading?`, `heading-level` |

#### 2.2 — Passe 2 : flux sections + affectation (`sections.clj`)

**Objectif** : un seul parcours linéaire des blocs (déjà en ordre de lecture) qui produit **à la fois** l'arbre de sections et l'affectation bloc→section.

**État du parcours** (par colonne — voir ci-dessous) :

```clojure
{:section-stack [{:id :level :title :column}]   ; pile hiérarchique
 :body-baseline {:max-font median :is-bold false} ; typo corps courante
 :column :left|:right                             ; colonne en cours
 :sections []                                     ; SectionRecord accumulés
 :block-assignments {block-id section-id}          ; affectation directe
 :heading-anchors [[page block-index] ...]}
```

**Contexte par colonne** : sur une page 2 colonnes COF2, chaque colonne a son propre fil de lecture. Au changement de `column-side`, on **ne propage pas** la section active de l'autre colonne — on reprend la section parente de la pile qui correspond à cette colonne, ou la section racine `"Document"` / dernière section chapitre de cette colonne.

**Pour chaque bloc** `(page, block-index, text, metadata)` en ordre de lecture :

| Étape | Action |
|-------|--------|
| 1 | Détecter changement de colonne → ajuster contexte section |
| 2 | Calculer `font-signal` vs `body-baseline` : Δ taille, passage gras, texte court |
| 3 | Si `heading-candidate?` (signal typo **+** garde-fous texte/visuels) → **nouvelle section** : pousser pile, enregistrer anchor, bloc **non chunké** |
| 4 | Sinon → **corps** : affecter `block-id → section-id` courant, mettre à jour `body-baseline` (moyenne glissante ou médiane locale) |
| 5 | Mettre à jour `page-end` de la section courante |

**Signal typo (cœur de la détection)** :

```clojure
(defn font-transition-heading?
  [block prev-block page median]
  ;; Corps → titre probable si :
  ;;   max-font >= median * 1.15 ET is-bold
  ;;   OU max-font >= prev max-font * 1.1 avec texte court (<= 14 mots, <= 120 car.)
  ;;   OU is-chapter-heading? / is-meta-box-heading? (regex prioritaire)
  ;; Rejeter si : spread décoratif, drop-cap, list-item, texte trop long
  ...)
```

Les regex et garde-fous COF2 (spread Momie p.5, `EN QUELQUES MOTS`, hooks `Si…`) restent nécessaires — le signal typo seul génère trop de faux positifs sur les fiches monstre (phase 5).

**Hiérarchie** : au moment d'ouvrir une section, `heading-level` + `heading-visual-tier` déterminent le `level` et le `parent-section-id` (chapitre vide la pile, subordinate s'accroche au chapitre actif de la colonne, etc.) — logique reprise de `sections.py` mais déclenchée **au fil de l'eau** plutôt qu'après scan global.

**Fallback** : aucun titre détecté → section unique `"Document"`, tous les blocs lui sont affectés.

#### 2.3 — Contrat de sortie

```clojure
{:sections [...]                                    ; SectionRecord
 :heading-anchors [[page block-index] ...]         ; ordre = ordre de lecture
 :block-assignments {"block_doc_005_003" "sec_..."}  ; NOUVEAU — clé pour phase 3
 :content-only-section-ids #{...}}                  ; si préambule « Introduction » conservé
```

`block-assignments` évite de recalculer « dernier anchor avant bloc en même colonne » en phase 3 — l'affectation est déjà faite en passe 2.

#### 2.4 — Fichiers

| Fichier | Rôle |
|---------|------|
| `reading_order.clj` | Passe 1 : `normalize-reading-order`, clés de tri, garde-fous géométrie/texte |
| `sections.clj` | Passe 2 : `assign-sections` (flux + détection + affectation) |
| `test/.../reading_order_test.clj` | Tri colonne-majeur page 7 Momie, colonnes non entremêlées |
| `test/.../sections_test.clj` | Cas portés depuis `test_sections.py` + affectation bloc→section |
| `test/.../test_fixtures/layout.clj` | `make-block`, `make-page` |

#### 2.5 — Sous-tâches

| # | Tâche | Done quand |
|---|-------|------------|
| 2.5.1 | `column-major-sort-key` + `normalize-reading-order` | test page 7 : index croît en colonne-majeur |
| 2.5.2 | Intégrer passe 1 dans `page.clj` (remplace tri `(y0,x0)`) | `extract_test` verts + ordre vérifié Momie |
| 2.5.3 | `font-transition-heading?` + garde-fous | tests spread p.5, drop-cap, meta box |
| 2.5.4 | `assign-sections` flux mono-colonne | tests chapitres simples + fallback Document |
| 2.5.5 | Contexte bi-colonne (pile par colonne) | tests PARTIE I/II, page 8 sans faux préambule |
| 2.5.6 | `block-assignments` + hiérarchie (subordinates, numérotés) | tests nesting `Les abattoirs` / `1 - Cave` |

#### 2.6 — Tests et oracle

**Priorité** : tests portés depuis `test_sections.py` (structure sections) **+** assertions sur `block-assignments` (chaque bloc corps pointe vers la bonne `section-id`).

**Oracle Python** : utile en dev pour comparer sections ; l'affectation bloc→section Python passe par `chunking.py` (logique différente) — ne pas viser une égalité bit-à-bit, seulement cohérence structurelle Momie.

**Test clé Momie p.5** : 3 sections (`EN QUELQUES MOTS`, `FICHE TECHNIQUE`, `LES GRANDES LIGNES`) + 3 blocs corps affectés — préfigure directement la phase 3.

#### 2.7 — Critères de done

- [ ] `block-index` = ordre de lecture colonne-majeur après extraction
- [ ] `assign-sections` retourne sections + `block-assignments` + anchors
- [ ] Tests `test_sections.py` portés (structure hiérarchique)
- [ ] Test affectation page 5 : 3 sections, 3 blocs corps correctement assignés
- [ ] Pipeline phase 0 branché sur passe 1 uniquement (passe 2 pas encore en prod)

#### 2.8 — Comparaison avec Python

| | Python actuel | Clojure cible |
|--|---------------|---------------|
| Ordre blocs | Ordre extraction + merge ; tri colonne-majeur seulement au chunking | **Passe 1** normalise dès l'extraction |
| Sections | Scan global → tri spatial titres → pile | **Passe 2** flux linéaire |
| Affectation | Rétrospective dans `chunking.py` | **Passe 2** simultanée (`block-assignments`) |
| Signal titre | Règles explicites par type | **Transition typo** + garde-fous |

---

### Phase 3 — Chunks 1:1

**`chunks.clj`** — trivialisé par la passe 2 :

```
1. Pour chaque bloc avec une entrée dans block-assignments :
     créer un chunk 1:1 (texte du bloc, section-id déjà connu)
2. Blocs anchor (titres) → pas de chunk
3. refine-section-page-ends depuis les spans des chunks
```

Plus besoin de recalculer « dernier anchor avant bloc en même colonne » — c'est fait en phase 2.

**Structure chunk** :
```clojure
{:id (chunk-id document-id page block-index)
 :section-id (get block-assignments block-id)
 :page-start page :page-end page
 :text (reflow-text block-text)
 :token-count (estimate-tokens text)
 :source-spans [{:page p :page-block-ids [block-id] :bbox ...}]
 :chunk-type-hint nil
 :metadata {}
 :needs-rechunk false}
```

**Critère de done** : test porté `test_build_chunks_partitions_blocks_between_headings_on_same_page` — 3 chunks, signatures uniques, textes `Résumé court.` / `Niveau 5` / `Contenu principal.`

---

### Phase 4 — Pipeline complète

**`pipeline.clj`** — équivalent de `importer.run()` mode `full` :

1. Hash PDF → `document-id`
2. `ensure-campaign`, `create-run` (`status: running`)
3. `extract-document` (PDFBox)
4. Coverage → `rejected` si scan
5. `delete-document-raw-data` si reimport
6. `normalize-reading-order` sur chaque page (passe 1)
7. Matérialiser `pages` + `page_blocks`
8. `assign-sections` (passe 2 — sections + block-assignments)
9. `build-chunks-1to1` depuis `block-assignments`
10. `refine-section-page-ends`
11. `insert-*` en transaction
12. `update-run` (`status: completed`, stats JSON)

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
4. **Python comme oracle temporaire** — comparer structure sections sur Momie ; l'affectation bloc→section n'a pas d'équivalent direct (chunking Python rétrospectif)

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
