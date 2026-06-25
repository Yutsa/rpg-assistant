# rpg-ingest-clj

Extraction PDFBox en Clojure : bandes Y puis séparation par gaps horizontaux.

## Prérequis

- Java 21+
- Clojure CLI 1.12+

## Extraction d'une page (JSON)

```bash
cd packages/ingest-clj
clojure -M:ingest raw extract-page --pdf /path/to/document.pdf --page 1
```

## Import phase 0 (pages + blocs → SQLite)

```bash
cd packages/ingest-clj
clojure -M:ingest import --pdf /path/to/document.pdf --campaign-id momie \
  --db sqlite:../../data/rpg_assistant.db
```

Persistance **pages + page_blocks** uniquement (pas sections/chunks). Sans appel Python.

Preuves d'acceptation : `proof/screenshots/` (générées via `proof/generate_proof.py` + `proof/phase0-proof.html`).

Mode serveur (JVM chaude, utilisé par l'API Python) :

```bash
clojure -M:ingest serve
# puis une requête JSON par ligne sur stdin : {"pdf":"/path/to.pdf","page":1}
```

Sortie JSON : `page_number`, `width`, `height`, `blocks[]` avec `block_index`, `text`, `bbox`, `metadata`.

Utilisé par l'API `GET /documents/{id}/pages/{n}/extractors-compare` et le viewer de comparaison PyMuPDF / PDFBox dans la webapp.

## Tests

```bash
cd packages/ingest-clj
clojure -M:test
```

## Périmètre actuel

- PDFBox `PDFTextStripper` avec `setSortByPosition true`
- Regroupement des `TextPosition` en bandes Y (tolérance 2 pt), puis split par gap horizontal adaptatif entre glyphes voisins
- Filtrage parasite (DRM, numéros de page, en-têtes) au niveau page

## Roadmap

Plan d'ingestion full 100 % Clojure (sections, chunks 1:1, persistance SQLite) : [`docs/plan-clojure-ingestion-full.md`](../../docs/plan-clojure-ingestion-full.md).
