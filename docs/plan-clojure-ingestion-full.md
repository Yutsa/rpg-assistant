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
│   ├── stat_blocks.clj         # phase 5 : détection fiches monstre/PNJ (heuristique dédiée)
│   ├── ids.clj                 # doc_*, block_*, sec_*, chunk_*, run_*
│   ├── pipeline.clj            # orchestration import full
│   └── storage/
│       ├── db.clj              # connexion SQLite
│       └── raw.clj             # INSERT campaigns…chunks
```

Plus tard (hors ce plan) : `api/`, `mcp/`, `semantic/`.

**Fiches monstre / PNJ (COF2)** : ignorées en phases 2–4. Une **étape dédiée** `detect-stat-blocks` sera branchée dans la chaîne en phase 5 (après chunks, ou en pré-filtre avant sections — à trancher à l'implémentation).

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

**Hors scope phases 2–4** :
- Fiches monstre / PNJ COF2 — pas de `false-heading?`, pas de `stat_block_role`, pas de garde-fous spécifiques fiches ; les blocs de fiches passent dans le flux sections/chunks comme du texte normal (imperfections acceptées)
- `insert-sections!` / `insert-chunks!` → phase 4

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

Les regex et garde-fous COF2 (spread Momie p.5, `EN QUELQUES MOTS`, hooks `Si…`, drop-cap, listes) suffisent pour la narration — **sans** traiter les faux positifs liés aux fiches monstre (nom en gras, NC, stats), reportés à la phase 5.

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

**Oracle Python** : utile en dev pour comparer sections sur le **texte narratif** ; ne pas benchmarker les pages à fiches monstre avant phase 5.

**Test clé Momie p.5** : 3 sections (`EN QUELQUES MOTS`, `FICHE TECHNIQUE`, `LES GRANDES LIGNES`) + 3 blocs corps affectés — p