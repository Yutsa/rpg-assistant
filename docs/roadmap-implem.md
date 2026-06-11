# Roadmap implémentation — Webapp de visualisation/exploration

État des lieux et découpage des prochaines user stories pour le MVP de la webapp de visualisation/exploration de campagne.

## État des lieux — où on en est

Le projet a aujourd'hui **deux surfaces seulement** : la CLI `rpg-ingest` et le serveur MCP `rpg-assistant`. **Il n'existe aucune webapp, aucune API HTTP, aucun frontend.** Tout le reste est une couche d'ingestion solide sur laquelle s'appuyer.

### Ce qui est fait et fonctionne

| Domaine | État | Détail |
|---|---|---|
| **Ingestion raw (déterministe)** | ✅ Mûr | PDF → pages, blocs avec bbox, sections (hiérarchie), chunks. Gestion bi-colonnes COF2, fusion de blocs, ordre de lecture, filtrage des numéros de page. Rejet des PDF scannés (`text_coverage_ratio`). |
| **Fiches de stats COF2** | ✅ | Détection + parsing structuré (NC, capacités…), index `list_stat_blocks` / `get_stat_block`. |
| **Stockage** | ✅ | SQLite + Postgres, schéma Alembic complet : `campaigns, documents, pages, page_blocks, sections, chunks, entities, entity_source_refs, entity_relations, extraction_reviews, correction_attempts`. |
| **Couche sémantique (écriture)** | 🟡 Partiel | Schémas + soumission via MCP (`submit_chunk_classifications/entities/relations`), validation déterministe (source refs, fuites GM-only, confiance, chunks/entités inconnus). |
| **Rendu source** | 🟡 Partiel | `render_pdf_pages` (PDF → PNG avec cache), bbox stockées. Utilisé pour la visual review, pas exposé au web. |
| **Boucle de revue visuelle** | ✅ | Échantillonnage + rendu pour vérifier l'ingestion. |

### Les manques bloquants pour une webapp d'exploration

1. **Aucune API HTTP** — la logique de lecture n'existe que dans les repositories Python, appelés par MCP/CLI. Rien n'est servi en HTTP.
2. **Lecture sémantique incomplète** — `SemanticRepository` ne sait pas relire une entité complète (avec ses `source_refs`) ni lister les entités/relations pour affichage. Il n'expose que des compteurs (`get_semantic_summary`), des `id`, et `player_safe`. Il faut des méthodes de lecture.
3. **Aucune recherche** — pas de full-text ni d'embeddings/pgvector (mentionnés dans les docs, absents du code). Or la vision MVP liste « searchable source chunks ».
4. **Pas d'extraction sémantique automatisée** — les entités/relations n'existent que si un agent les a soumises à la main via MCP. La base de dev démarre sans entités. La webapp risque d'avoir des écrans vides côté entités.
5. **Pas d'assets/maps** — les pages image-only (plans, cartes de *Mondanités et Momie* p.6/19) ne sont pas extraites (extension Stage 1 documentée mais non faite).
6. **Pas de reveal tracking ni de notes** — `campaign_state` / `session_notes` existent dans la doc mais **pas** dans la migration. C'est du Stage 2 (GM Workspace), hors MVP visualisation.

---

## Décisions d'architecture (verrouillées)

- **Backend** : FastAPI, qui réutilise directement les modèles Pydantic et les repositories existants (`RawRepository`, `SemanticRepository`). OpenAPI auto pour cadrer le contrat front/back.
- **Déploiement** : local-first. L'app tourne sur la machine du MJ, le PDF source ne quitte jamais le poste → cohérent avec les contraintes copyright de la vision produit. Implique : serveur FastAPI local (ex. `uvicorn` lancé par un script `rpg-web`), front buildé servi en statique, chemins PDF résolus en local.
- **Données entités** : extraction agent (MCP) sur `momie` pour développer l'axe 4 contre des données réelles.

---

## Prérequis avant de lancer (chaîne de dépendances pour `momie`)

La base est vide par défaut, donc avant de poupler les entités :

1. `cp .env.example .env` puis `uv run alembic upgrade head` (crée `data/rpg_assistant.db`).
2. Importer le **PDF de `momie`** (propriétaire, non commité — doit être en local) :
   ```bash
   uv run rpg-ingest raw extract <momie.pdf> --campaign-id momie --game-system cof2
   ```
   Ça reconstruit `doc_010672301b36` et le raw.
3. Lancer la passe d'enrichissement agent via MCP :
   - `submit_chunk_classifications`
   - `submit_entities` avec `source_refs`
   - `submit_relations`
   - `validate_semantic_layer`

⚠️ Sans le PDF `momie` en local, l'axe 4 reste bloqué : dans ce cas, démarrer par les axes 1→3 (raw : sections/chunks/stat blocks) qui n'ont besoin que de l'import raw.

---

## Découpage proposé pour le MVP webapp

Le MVP « visualisation/exploration » est par nature **en lecture seule** : naviguer la campagne, lire le texte source, explorer les entités et leurs liens, vérifier dans le PDF. Le reveal tracking, les notes et l'édition relèvent du Stage 2.

7 axes (epics). Les axes 1→4 sont le cœur du MVP et doivent être faits dans l'ordre ; 5→7 sont des incréments de valeur.

### Axe 0 — Décision d'architecture (préalable)

Avant de lancer : choisir la stack frontend (ex. React/Vite ou SvelteKit). Décider local-first vs serveur (cf. enjeux copyright des PDF). Décider si on génère un vrai jeu d'entités de démo (lancer l'extraction agent sur `momie`) pour ne pas développer contre des écrans vides.

**Décisions prises** : FastAPI, local-first, peuplement entités via agent MCP sur `momie`.

### Axe 1 — API de lecture (backend) 🔴 fondation

- **US1.1** — En tant que front, je peux lister les campagnes et documents (`GET /campaigns`, `/campaigns/{id}/documents`). *Repos déjà prêts.*
- **US1.2** — Je peux récupérer l'arbre des sections d'un document (`GET /documents/{id}/sections`). *Prêt.*
- **US1.3** — Je peux lister/paginer/filtrer les chunks et lire un chunk complet (`GET /documents/{id}/chunks`, `/chunks/{id}`). *Prêt.*
- **US1.4** — Je peux lister/lire les fiches de stats (`GET /documents/{id}/stat-blocks`, `/stat-blocks/{name}`). *Prêt.*
- **US1.5** — **Nouvelles méthodes repo** : lire les entités (avec `source_refs`), filtrer par type, et lire les relations d'une entité. *À développer dans `SemanticRepository`.*
- **US1.6** — `GET /campaigns/{id}/summary` (compteurs ingestion + sémantique). *Quasi prêt.*

### Axe 2 — Affichage source PDF 🔴 différenciateur clé

- **US2.1** — Servir la page PDF rendue en image (`GET /documents/{id}/pages/{n}/render?dpi=`). *Réutilise `render_pdf_pages`.*
- **US2.2** — Renvoyer les blocs/bbox d'une page pour dessiner les surlignages (`GET /documents/{id}/pages/{n}/blocks`).
- **US2.3** — Côté front : vue page rendue + overlay des bbox (conversion coords PDF → viewport).
- **US2.4** — Gérer la résolution du chemin du PDF source (stocké dans les stats du run ; définir où vivent les PDF utilisateurs).

### Axe 3 — Frontend exploration cœur 🔴

- **US3.1** — Sélecteur de campagne / document (landing).
- **US3.2** — Navigateur de structure : arbre des sections, clic → liste des chunks de la section.
- **US3.3** — Lecteur de chunk : texte + métadonnées + bouton « voir la source » (ouvre l'axe 2 en side-by-side).
- **US3.4** — Pages de fiches de stats COF2 (rendu structuré lisible).
- **US3.5** — Layout général, état de chargement, navigation, responsive.

### Axe 4 — Exploration des entités 🟠 (dépend d'entités peuplées)

- **US4.1** — Index des entités filtrable par type (NPC, lieu, faction, secret, indice, objet…).
- **US4.2** — Page détail entité : résumé, `player_safe` vs `gm_only` séparés visuellement (toggle spoiler), aliases, confiance.
- **US4.3** — Liens « source » de l'entité → chunk + page PDF surlignée (réutilise axe 2).
- **US4.4** — Affichage des relations entrantes/sortantes d'une entité (liste typée).

### Axe 5 — Recherche 🟠

- **US5.1** — Recherche plein-texte sur chunks (FTS5 SQLite / `tsvector` Postgres) — `GET /campaigns/{id}/search?q=`.
- **US5.2** — Recherche sur les entités (nom/aliases/résumé).
- **US5.3** — (Optionnel/ultérieur) embeddings + recherche sémantique (pgvector) — gros chantier, candidat à différer.

### Axe 6 — Vue graphe de relations 🟢 (nice-to-have MVP)

- **US6.1** — `GET /campaigns/{id}/graph` (nœuds entités + arêtes relations).
- **US6.2** — Visualisation interactive (clic nœud → page détail). *Question ouverte de la vision : graphe nécessaire au MVP ou plus tard ?*

### Axe 7 — Assets / cartes 🟢 (extension Stage 1)

- **US7.1** — Détecter les pages image-only à l'ingestion + stocker l'asset lié à `page_id` (table `document_assets` + migration).
- **US7.2** — Servir et afficher les cartes/handouts dans le workspace.

---

## Recommandation de séquencement

| Sprint | Contenu | Résultat attendu |
|---|---|---|
| **Sprint 1** | Axe 1 + Axe 2 backend | API de lecture + endpoints PDF/bbox |
| **Sprint 2** | Axe 3 + front Axe 2 | Webapp utile sur le raw (sections/chunks/stat blocks + side-by-side PDF) |
| **Sprint 3** | Axe 4 + Axe 5.1/5.2 | Exploration entités + recherche plein-texte |
| **Backlog** | Axe 6, Axe 7, US5.3, Stage 2 | Graphe, cartes, embeddings, notes, reveal tracking, édition |

---

## Hors scope MVP visualisation (Stage 2+)

Référence : `docs/product-vision.md` — Stage 2 « GM Workspace ».

- Reveal tracking (ce que les joueurs savent)
- Notes de session / annotations privées
- Édition manuelle des entités extraites
- Mode session live
- AI Prep Assistant (Stage 3) et au-delà

---

## Références

- Vision produit : `docs/product-vision.md`
- Modèle technique ingestion : `docs/technical-ingestion.md`
- Workflow agent / MCP : `AGENTS.md`
- Campagne de référence dev : `campaign_id=momie`, `document_id=doc_010672301b36`
