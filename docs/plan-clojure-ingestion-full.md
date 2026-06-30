# Plan : pipeline d'ingestion full en Clojure

## Suivi d'avancement (pour les agents)

> **Prompt utilisateur typique** : « Continue l'implémentation de la prochaine phase du plan. »
>
> Lire cette section en premier, puis la section détaillée de la phase listée dans **Prochaine phase**.

| Phase | Intitulé | Statut | Livrable principal |
|-------|----------|--------|-------------------|
| 0 | Fondations (storage, CLI import pages+blocs) | ✅ fait | `storage/raw.clj`, `pipeline.clj` (phase 0) |
| 1 | Metadata `:is-bold` | ✅ fait | `extract/page.clj` |
| 2 | Ordre de lecture + sections | ✅ fait | `reading_order.clj`, `sections.clj`, tests |
| 3 | Chunks 1:1 | ✅ fait | `chunks.clj`, `text/reflow.clj`, tests — PR #42 |
| **4** | **Pipeline complète** | **✅ fait** | **`pipeline.clj` full, `insert-sections!` / `insert-chunks!`, `coverage.clj`** |
| 5 | Fiches monstre (profils jeu) | ✅ fait | `stat_blocks/` — Malli + multimethodes, profil `:cof2` |
| 6 | API / MCP / sémantique | hors scope | — |

### Prochaine phase : **6 — API / MCP / sémantique** (hors scope ingestion raw)

**Objectif** : framework **profil par jeu** (Malli pour les formes de données, **multimethodes** pour le dispatch) ; première implémentation **`:cof2`**, extensible à d'autres jeux.

**Fichiers à modifier / créer** :

| Fichier | Action |
|---------|--------|
| `stat_blocks/schema.clj` | **Nouveau** — schémas Malli (`StatBlockSpan`, `ParsedStatBlock`, …) |
| `stat_blocks/registry.clj` | **Nouveau** — `resolve-profile` depuis `--game-system` + aliases |
| `stat_blocks/core.clj` | **Nouveau** — `defmulti` + `annotate-stat-blocks` |
| `stat_blocks/cof2.clj` | **Nouveau** — `defmethod` `:cof2` (port de `cof2.py`) |
| `stat_blocks/generic.clj` | **Nouveau** — `defmethod` `:generic` (fallback minimal) |
| `stat_blocks/text_utils.clj` | **Nouveau** — glyphes icônes, strip layout |
| `pipeline.clj` | Résoudre profil, annoter fiches, chaîne complète |
| `sections.clj` | `is-false-heading?` via profil actif |
| `block-merging.clj` | Ne pas fusionner les blocs de fiche |
| `chunks.clj` | Exclure blocs fiche du 1:1 ; `materialize-stat-chunks` |
| `test/.../stat_blocks_test.clj` | Tests fiches Momie |

**Critères de done** : profil `:cof2` opérationnel ; fiches Momie sur ≥ 2 pages ; sections adjacentes non polluées ; chunks `stat_block` avec metadata compatible API/MCP.

**Tests** :

```bash
cd packages/ingest-clj && clojure -M:test
```

**Dernière mise à jour du suivi** : 2026-06-28 (phase 5 livrée — profils `:cof2` / `:generic`, chunks `stat_block`).

---

## Objectif

Remplacer entièrement la pipeline Python d'ingestion raw (`rpg-ingest`, provider PyMuPDF) par une pipeline **100 % Clojure** (PDFBox). L'API et le MCP seront réécrits en Clojure plus tard ; ce plan couvre uniquement l'ingestion jusqu'à la persistance SQLite.

**Hors scope immédiat** : comparateur PyMuPDF/PDFBox (`extractor-compare`), couche sémantique, API HTTP, MCP.

## Modèle de données retenu

| Couche | Rôle | Règle |
|--------|------|-------|
| **Blocs** | Extraction layout (texte + bbox + metadata typo) | Produits par `extract/page.clj` |
| **Sections** | Structure hiérarchique du document | Blocs-titres ; pas de chunk |
| **Chunks** | Unité de contenu exposée (future API/MCP) | **Narratif** : 1 bloc = 1 chunk. **Fiches** (phase 5) : 1 span fiche = 1 chunk `stat_block` (exception explicite) |

Enrichissement sémantique ultérieur : `section_id`, `chunk_type`, metadata (texte MJ, texte à lire aux joueurs, etc.).

Le schéma SQLite existant (`campaigns`, `documents`, `ingestion_runs`, `pages`, `page_blocks`, `sections`, `chunks`) est **conservé tel quel** pour compatibilité avec la webapp et les outils actuels.

## État actuel

| Composant | Statut |
|-----------|--------|
| Extraction PDFBox page par page | ✅ `packages/ingest-clj` |
| Blocs (texte, bbox, metadata) | ✅ |
| Metadata `:is-bold` alignée Python | ✅ phase 1 |
| CLI `extract-page` / `extract-document` / `serve` | ✅ |
| Persistance SQLite depuis Clojure | ✅ phase 0 (pages + blocs) |
| Ordre de lecture (passe 1) | ✅ `reading_order.clj` — tri spatial `(x0, y0, x1)` |
| Sections + `block-assignments` (passe 2) | ✅ `sections.clj` |
| Chunks 1:1 | ✅ `chunks.clj` (phase 3) |
| Import `full` sans Python | ✅ phase 4 |
| Fiches monstre (profils jeu) | ❌ **phase 5** |

Aujourd'hui, `import-pdf!` persiste **pages, blocs, sections et chunks narratifs** (phase 4). Les blocs de fiches monstre passent encore dans le flux sections/chunks sans traitement dédié — d'où les faux titres et chunks fragmentés sur les pages COF2. Le comparateur extracteur reste un pont Python (`clojure_pdfbox.py`, outil dev).

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
│   ├── reading_order.clj       # passe 1 : tri spatial (x0, y0), garde-fous géométrie
│   ├── sections.clj            # passe 2 : flux typo → sections + block-assignments
│   ├── chunks.clj              # blocs narratifs → chunks 1:1 ; materialize-stat-chunks
│   ├── stat_blocks/            # phase 5 : profils fiche monstre/PNJ
│   │   ├── schema.clj          # Malli : StatBlockSpan, ParsedStatBlock, …
│   │   ├── registry.clj        # resolve-profile (game-system → keyword profil)
│   │   ├── core.clj            # defmulti + annotate-stat-blocks
│   │   ├── cof2.clj            # defmethod :cof2
│   │   ├── generic.clj         # defmethod :generic
│   │   └── text_utils.clj
│   ├── ids.clj                 # doc_*, block_*, sec_*, chunk_*, run_*
│   ├── pipeline.clj            # orchestration import full
│   └── storage/
│       ├── db.clj              # connexion SQLite
│       └── raw.clj             # INSERT campaigns…chunks
```

Plus tard (hors ce plan) : `api/`, `mcp/`, `semantic/`.

**Fiches monstre / PNJ** : ignorées en phases 2–4. Phase 5 : **profil par jeu** (`:cof2` en premier) via multimethodes ; annotation des blocs **avant** `assign-sections` (aligné Python).

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

**Décision** : pas d'exposition de `:column` en metadata. L'ordre de lecture est imposé par le tri spatial en passe 1 ; en passe 2, un **fil de lecture** (cluster x) peut être dérivé à la volée pour la pile de sections — sans nommer « colonne COF2 » dans les metadata bloc. `page-median-font` calculé à la volée en passe 2 (pas stocké en metadata).

**Livré** (`page.clj`, PR #37) :
- `:is-bold` dans les metadata bloc (JSON persisté : `is_bold`, aligné Python).
- `:bold?` supprimé des metadata exposées.

---

### Phase 2 — Ordre de lecture + sections (deux passes) ✅

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

**Objectif** : garantir que `block-index` reflète un ordre de lecture cohérent **avant** toute détection de section — avec une règle **générique** (pas de layout « colonnes COF2 » codé en dur).

##### Décision : tri spatial `(x0, y0)`

Clé de tri par bloc (par page) :

```clojure
(defn spatial-sort-key [block]
  [(get-in block [:bbox :x0])
   (get-in block [:bbox :y0])
   (get-in block [:bbox :x1])])  ; tie-breaker
```

| Tri | Comportement | 1 colonne | 2 colonnes (COF2) |
|-----|--------------|-----------|-------------------|
| **`(y0, x0)`** ❌ | Bande horizontale : haut→bas, puis gauche→droite **à même hauteur** | ✓ | ✗ entremêle gauche/droite (ex. Momie p.7 : « Depuis lors » entre deux blocs MJ) |
| **`(x0, y0)`** ✅ retenu | D'abord position horizontale, puis verticale | ✓ (x0 stable → ordre = y0) | ✓ (deux clusters x : fil gauche entier, puis fil droit) |
| **`column-side` + y0** | Colonne nommée via centre x vs milieu page | ⚠️ blocs pleine largeur peuvent sauter à la fin du fil | ✓ mais hypothèse layout spécifique |

**Pourquoi pas `column-side` en passe 1** : sur une page 1 colonne, un titre pleine largeur dont le centre dépasse `page-width/2` est classé « droite » et relu **après** tout le corps — ordre faux. `(x0, y0)` évite cette catégorisation.

**Effet attendu** (Momie p.7) : blocs `x0≈43` par y croissant, puis blocs `x0≈248` par y croissant — sans appeler explicitement « colonne ».

##### API

```clojure
(defn sort-blocks-spatial [blocks]
  (vec (sort-by spatial-sort-key blocks)))

(defn reindex-blocks [blocks]
  (vec (map-indexed #(assoc %2 :block-index %1) blocks)))

(defn normalize-page-blocks [blocks]
  (-> blocks sort-blocks-spatial reindex-blocks))

(defn normalize-reading-order [pages]
  (mapv #(update % :blocks normalize-page-blocks) pages))
```

**Où appeler** : en fin de `page-blocks` (`page.clj`) et sur `extract-document` (`pdf.clj`) — les IDs `block_*` reflètent l'ordre en base.

**Ne pas** réintroduire un tri `(y0, x0)` global dans `merge-segments-by-font` : la fusion de paragraphes peut regrouper par bande x (heuristique extraction), mais l'**index final** passe toujours par `normalize-page-blocks`.

**Conséquence** : réimport nécessaire pour les documents BDD phase 0 dont l'index ≠ ordre spatial.

##### Utilitaires `reading_order.clj` (passe 1 + réutilisés en passe 2)

| Groupe | Fonctions | Passe |
|--------|-----------|-------|
| Tri | `spatial-sort-key`, `sort-blocks-spatial`, `normalize-page-blocks`, `spatial-ordered?` | 1 |
| Géométrie | `horizontal-overlap-ratio`, `is-in-column-band?` | 2 (affectation / fils parallèles) |
| Typo page | `page-median-font` | 2 |
| Texte / titres | `strip-glyphs`, regex, `is-meta-box-heading?`, `heading-level`, … | 2 |
| Rejets visuels | `is-decorative-spread-title?`, `is-vertical-running-header?`, … | 2 |

`is-in-column-band?` reste utile en **passe 2** pour savoir si deux blocs partagent le même fil de lecture ; il ne sert **pas** à réordonner les blocs en passe 1.

##### Tests passe 1

| Test | Attendu |
|------|---------|
| Synthétique 2 clusters x | `(x0,y0)` place tout `x=40` avant tout `x=260`, même si droite commence plus haut en y |
| PDF 1 colonne synthétique | indices croissants = y croissant |
| Momie p.7 | `spatial-ordered?` ; idx 0–3 `x0<120` ; idx 4+ `x0>200` ; y croissant dans chaque cluster |
| `extract_test` existants | pas de régression extraction |

#### 2.2 — Passe 2 : flux sections + affectation (`sections.clj`)

**Objectif** : un seul parcours linéaire des blocs (déjà en ordre de lecture) qui produit **à la fois** l'arbre de sections et l'affectation bloc→section.

**État du parcours** :

```clojure
{:section-stack [{:id :level :title :stream-x}]  ; pile hiérarchique par fil de lecture
 :body-baseline {:max-font median :is-bold false}
 :stream-x nil                                   ; x0 de référence du fil en cours
 :sections []
 :block-assignments {block-id section-id}
 :heading-anchors [[page block-index] ...]}
```

**Fils de lecture parallèles** : sur une page multi-clusters x (ex. 2 colonnes COF2), quand le `x0` du bloc courant n'est plus dans la même bande que le fil actif (`is-in-column-band?` avec le bloc de référence, ou saut significatif de `x0`), on **change de fil** — on ne propage pas la section active de l'autre bande. Pas besoin du concept nommé « colonne » : le cluster x suffit.

**Détection de changement de fil** (heuristique simple) :

```clojure
(defn same-reading-stream? [ref-block block]
  (is-in-column-band? block ref-block))
;; Au début de chaque page ou quand same-reading-stream? est false :
;; reprendre la section racine ou la dernière section ouverte sur ce fil (stream-x).
```

**Pour chaque bloc** `(page, block-index, text, metadata)` en ordre de lecture :

| Étape | Action |
|-------|--------|
| 1 | Si changement de fil (`x0` / `is-in-column-band?`) → ajuster pile section pour ce fil |
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

**Hiérarchie** : au moment d'ouvrir une section, `heading-level` + `heading-visual-tier` déterminent le `level` et le `parent-section-id` (chapitre vide la pile du fil courant, subordinate s'accroche au chapitre actif sur ce fil, etc.).

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
| `test/.../reading_order_test.clj` | Tri `(x0,y0)` : synthétique, 1 colonne, Momie p.7 |
| `test/.../sections_test.clj` | Cas portés depuis `test_sections.py` + affectation bloc→section |
| `test/.../test_fixtures/layout.clj` | `make-block`, `make-page` |

#### 2.5 — Sous-tâches

| # | Tâche | Done quand |
|---|-------|------------|
| 2.5.1 | `spatial-sort-key` + `normalize-reading-order` | ✅ |
| 2.5.2 | Intégrer passe 1 dans `page.clj` | ✅ `extract_test` + `reading_order_test` verts |
| 2.5.3 | `font-transition-heading?` + garde-fous | tests spread p.5, drop-cap, meta box |
| 2.5.4 | `assign-sections` flux mono-fil (1 colonne) | tests chapitres simples + fallback Document |
| 2.5.5 | Fils parallèles (`is-in-column-band?`) | tests PARTIE I/II, page 8 sans faux préambule |
| 2.5.6 | `block-assignments` + hiérarchie (subordinates, numérotés) | tests nesting `Les abattoirs` / `1 - Cave` |

#### 2.6 — Tests et oracle

**Priorité** : tests portés depuis `test_sections.py` (structure sections) **+** assertions sur `block-assignments` (chaque bloc corps pointe vers la bonne `section-id`).

**Oracle Python** : utile en dev pour comparer sections sur le **texte narratif** ; ne pas benchmarker les pages à fiches monstre avant phase 5.

**Test clé Momie p.5** : 3 sections (`EN QUELQUES MOTS`, `FICHE TECHNIQUE`, `LES GRANDES LIGNES`) + 3 blocs corps affectés — préfigure directement la phase 3. Pages avec fiches PNJ : hors critères de done phase 2.

#### 2.7 — Critères de done

- [x] `block-index` = ordre tri spatial `(x0, y0, x1)` après extraction
- [x] `assign-sections` retourne sections + `block-assignments` + anchors
- [x] Tests `test_sections.py` portés (structure hiérarchique) → `sections_test.clj`
- [x] Test affectation page 5 : 3 sections, 3 blocs corps correctement assignés
- [x] Passe 1 branchée dans `page.clj` / `pdf.clj`

#### 2.8 — Comparaison avec Python

| | Python actuel | Clojure cible |
|--|---------------|---------------|
| Ordre blocs | Ordre extraction + merge ; `column_major_sort_key` au chunking | **Passe 1** : `(x0, y0)` dès l'extraction |
| Sections | Scan global → tri spatial titres → pile | **Passe 2** flux linéaire |
| Affectation | Rétrospective dans `chunking.py` | **Passe 2** simultanée (`block-assignments`) |
| Signal titre | Règles explicites par type | **Transition typo** + garde-fous |
| Fils parallèles | `is-in-column-band?` au chunking | Même utilitaire en passe 2, pas en passe 1 |

---

### Phase 3 — Chunks 1:1 ✅

**Livré** : `chunks.clj`, `text/reflow.clj`, `chunks_test.clj` (PR #42).

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
 :text (reflow-text block-text)   ; nettoyage retours ligne / césures PDF — pas de re-découpage
 :source-spans [{:page p :page-block-ids [block-id] :bbox ...}]
 :chunk-type-hint nil
 :metadata {}
 :needs-rechunk false}
```

Le reflow aligne le texte chunk sur la pipeline Python (`reflow_chunk_text`) : espaces insécables, fusion des `\n` intra-paragraphe, césures en fin de ligne. Il ne fusionne **pas** de blocs — le 1:1 est entièrement porté par `block-assignments`.

**Critères de done** :

- [x] `build-chunks-1to1` depuis `block-assignments`
- [x] `refine-section-page-ends`
- [x] Test porté `test_build_chunks_partitions_blocks_between_headings_on_same_page` → `chunks_test.clj`
- [x] Test `test_build_chunks_covers_all_blocks_without_duplicates` porté

### Phase 4 — Pipeline complète ✅

**Livré** : `pipeline.clj` full, `coverage.clj`, `insert-sections!` / `insert-chunks!`, tests intégration Momie.

**Critères de done** :

- [x] `insert-sections!` + `insert-chunks!` alignés schéma SQLite
- [x] Coverage → rejet si `text_coverage_ratio < seuil` (défaut 0.3)
- [x] `import-pdf!` enchaîne extract → sections → chunks → persist
- [x] Stats run : `section_count`, `chunk_count`, `text_coverage_ratio`
- [x] Test Momie : sections > 0, chunks > 0
- [x] CLI `--coverage-threshold`

### Phase 5 — Fiches monstre / PNJ (profils jeu) 🔲 **PROCHAINE**

**Objectif** : framework **extensible par jeu** pour détecter, parser et chunker les fiches monstre/PNJ. Pas de `defprotocol` : **Malli** pour valider les formes de données, **`defmulti` / `defmethod`** pour router le comportement par profil (`:cof2`, `:generic`, futurs jeux).

**Spécification Python** (référence comportementale, pas à copier mot pour mot) :

| Python | Clojure cible |
|--------|---------------|
| `stat_blocks/profile.py` (`Protocol`) | `stat_blocks/core.clj` (`defmulti` sur `:profile-id`) |
| `stat_blocks/registry.py` | `stat_blocks/registry.clj` |
| `stat_blocks/types.py` (`Pydantic`) | `stat_blocks/schema.clj` (`Malli`) |
| `stat_blocks/cof2.py` | `stat_blocks/cof2.clj` (`defmethod` `:cof2`) |
| `stat_blocks/generic.py` | `stat_blocks/generic.clj` (`defmethod` `:generic`) |

#### 5.1 — Formes de données (Malli)

Schémas dans `stat_blocks/schema.clj`, alignés sur `packages/ingest/.../stat_blocks/types.py` pour compatibilité API/MCP :

```clojure
;; Exemples — formes cibles, pas d'interface à implémenter
StatBlockSpan     ; {:id :blocks :page-start :page-end}
ParsedStatBlock   ; {:name :subtitle :nc :attributes :abilities :rulebook-reference …}
StatAbility       ; {:title :text}
BlockRef          ; {:page-number :block-index}
```

Validation via `rpg.ingest.schema/validate` aux frontières (sortie `detect-spans`, sortie `parse-span`).

Metadata bloc annotée en place (comme Python) : `stat_block_id`, `stat_block_role` (`"header"`, `"stats"`, `"icon"`, `"ability"`, …).

#### 5.2 — Dispatch par profil (multimethodes)

`stat_blocks/core.clj` déclare les multimethodes dispatchées sur le **keyword profil** (`:cof2`, `:generic`, …) :

| Multiméthode | Rôle |
|--------------|------|
| `matches-document?` | Auto-détection si `--game-system` absent ou inconnu |
| `detect-spans` | Parcourt les pages, annote les blocs, retourne `[StatBlockSpan …]` |
| `parse-span` | `StatBlockSpan` → `ParsedStatBlock` |
| `false-heading?` | Bloc à exclure de la détection de titre section |
| `normalize-block-text` | Nettoyage texte spécifique jeu (optionnel) |

`stat_blocks/registry.clj` :

```clojure
(resolve-profile game-system pages) → :cof2 | :generic | …
```

Résolution (identique Python) :

1. `--game-system` normalisé → alias map (`"cof2"`, `"chroniques oubliées fantasy 2"`, …)
2. Sinon essai `matches-document?` sur chaque profil enregistré (sauf `:generic`)
3. Sinon `:generic`

Nouveau jeu = nouveau namespace + `defmethod` + entrée dans le registre. Aucun protocole à étendre.

#### 5.3 — Chaîne pipeline (ordre cible)

```
extract-document
→ normalize-reading-order          ; passe 1 (déjà en place)
→ resolve-profile                  ; game-system + pages
→ merge-fragmented-pages           ; avec false-heading? du profil
→ annotate-stat-blocks             ; detect-spans + metadata blocs
→ assign-sections                  ; false-heading? du profil
→ build-chunks-1to1                ; blocs narratifs uniquement (hors stat_block_id)
→ materialize-stat-chunks          ; 1 span → 1 chunk stat_block
→ reassign-stat-block-sections     ; rattacher fiche à section narrative voisine
→ refine-section-page-ends
→ persist
```

**Points d'injection** (le profil n'est pas limité à `detect-spans`) :

| Module | Changement |
|--------|------------|
| `pipeline.clj` | `resolve-profile`, `annotate-stat-blocks`, stats `stat_block_count` / `stat_block_profile` |
| `block-merging.clj` | Ne pas fusionner les blocs annotés fiche |
| `sections.clj` | Appeler `false-heading?` du profil dans `heading-candidate?` |
| `chunks.clj` | Exclure blocs `stat_block_id` du 1:1 ; `materialize-stat-chunks` + `reassign-stat-block-sections` |

Chunk fiche produit :

```clojure
{:chunk-type-hint "stat_block"
 :metadata {:stat_block <ParsedStatBlock>
            :stat_block_span_id <span-id>}
 …}
```

Metadata compatible `rpg_core.stat_blocks` / `list_stat_blocks` / `get_stat_block` (API et MCP inchangés).

#### 5.4 — Profil `:cof2` (v1)

Port de `packages/ingest/.../stat_blocks/cof2.py` :

- Détection spans : nom + NC, lignes stats AGI/FOR/CON…, icônes glyphe, capacités
- `false-heading?` : header, stats, icône, nom en capitales, ligne NC
- `parse-span` : nom, subtitle, nc, attributes, abilities, rulebook-reference
- `matches-document?` : au moins 1 NC + 1 ligne stats sur le document

Référence tests : pages fiches Momie (≥ 2 pages distinctes).

#### 5.5 — Profil `:generic` (stub)

Fallback minimal (comme Python) : `detect-spans` → `[]`, `false-heading?` sur rôles annotés, `parse-span` → texte brut. Permet d'enregistrer un futur profil sans casser le pipeline.

#### 5.6 — Sous-tâches (checklist agent)

| # | Tâche | Fichier(s) | Done quand |
|---|-------|------------|------------|
| 5.6.1 | Schémas Malli | `stat_blocks/schema.clj` | `StatBlockSpan`, `ParsedStatBlock` validés |
| 5.6.2 | Registre + `resolve-profile` | `stat_blocks/registry.clj` | aliases COF2, fallback `:generic` |
| 5.6.3 | Multimethodes + `annotate-stat-blocks` | `stat_blocks/core.clj` | annotation metadata + liste spans |
| 5.6.4 | Implémentation `:cof2` | `stat_blocks/cof2.clj`, `text_utils.clj` | port heuristiques `cof2.py` |
| 5.6.5 | Implémentation `:generic` | `stat_blocks/generic.clj` | stub non régressif |
| 5.6.6 | `false-heading?` dans sections | `sections.clj` | noms monstre non titres |
| 5.6.7 | Merge + profil | `block-merging.clj` | blocs fiche non fusionnés |
| 5.6.8 | Chunks fiche | `chunks.clj` | `materialize-stat-chunks`, exclusion 1:1 |
| 5.6.9 | Réaffectation section | `chunks.clj` ou `stat_blocks/core.clj` | fiche rattachée section narrative |
| 5.6.10 | Orchestration | `pipeline.clj` | chaîne complète + stats run |
| 5.6.11 | Tests Momie | `stat_blocks_test.clj`, `import_test.clj` | ≥ 2 fiches, sections propres, chunks `stat_block` |

#### 5.7 — Critères de done

- [ ] `resolve-profile` + multimethodes opérationnels (`:cof2`, `:generic`)
- [ ] Fiches Momie reconnues sur **≥ 2 pages** ; sections adjacentes **non polluées**
- [ ] Chunks `stat_block` avec metadata structurée ; `list_stat_blocks` / `get_stat_block` alimentables sans changement API
- [ ] Stats run : `stat_block_count`, `stat_block_profile`
- [ ] Tests `clojure -M:test` verts

**Hors scope phase 5 initiale** : nouveaux profils jeu (D&D, etc.) ; `chunk_type_hint` narratif avancé ; tests audit complets `test_cof2_audit_*` ; `false-heading?` générique hors profil.

---

### Phase 6 — Au-delà (plus tard)

| Composant | Remplace |
|-----------|----------|
| Couche sémantique | `submit_chunk_classifications`, entités, relations |
| API HTTP | `rpg-api` |
| MCP | `rpg-assistant-mcp` |
| Rendu PDF / visual review | `rendering.py`, MCP `prepare_visual_ingestion_review` |

## Ce qu'il ne faut pas porter de Python

- `_group_blocks_for_chunking` / budget ~4800 caractères
- Mode `extractor-compare` / dual lanes (outil dev)
- `raw_layout_json` PyMuPDF (optionnel)
- Merge document-level (`merge_fragmented_blocks`, etc.) — réévaluer seulement si régressions sur blocs Clojure

## Stratégie de tests

1. **Unitaires Clojure** — PDF synthétiques (`test/rpg/ingest/test_fixtures/pdf.clj`)
2. **Intégration BDD** — import → requêtes SQL
3. **Régression COF2 narratif** — structure sections + chunks sur Momie (pages sans fiches en phases 2–4 ; fiches en phase 5)
4. **Python comme oracle temporaire** — comparer structure sections sur Momie ; l'affectation bloc→section n'a pas d'équivalent direct (chunking Python rétrospectif)

## Campagne de référence

| Clé | Valeur |
|-----|--------|
| `campaign_id` | `momie` |
| PDF | `data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf` |
| Page piège colonnes | **7** |

## Ordre de travail

```
Phase 0 (storage) → Phase 1 (is-bold) → Phase 2 (sections) → Phase 3 (chunks) → Phase 4 (pipeline full) → Phase 5 (fiches monstre)
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
| Stat blocks (profils) | `packages/ingest/.../stat_blocks/` | `packages/ingest-clj/.../stat_blocks/` (phase 5) |
| Profil COF2 | `.../stat_blocks/cof2.py` | `.../stat_blocks/cof2.clj` |
| Registre profils | `.../stat_blocks/registry.py` | `.../stat_blocks/registry.clj` |
| Schéma BDD | `migrations/versions/001_initial_schema.py` | inchangé |

## Comparateur extracteur (contexte)

L'**outil de dev** comparateur PyMuPDF/PDFBox (`--ingest-mode extractor-compare`, route `/extractors-compare`) reste disponible pour affiner `page.clj`. Ce n'est pas le chemin de production une fois la pipeline full Clojure en place.
