# rpg-ingest-clj

Extraction raw de PDF en Clojure (maps + Malli), sans heuristiques de structuration.

## Prérequis

- Java 21+
- Clojure CLI 1.12+

## Import d'un PDF

```bash
cd packages/ingest-clj
export DATABASE_URL=sqlite:////workspace/data/rpg_assistant.db
clojure -M:ingest raw extract \
  --pdf /path/to/document.pdf \
  --campaign-id my-campaign \
  --game-system cof2
```

La base SQLite doit exister (`uv run alembic upgrade head` à la racine du monorepo).

## Tests

```bash
cd packages/ingest-clj
clojure -M:test
```

## Périmètre v1

- Extraction layout PDFBox → pages + blocs (bbox, métadonnées typo)
- Détection double colonne : positions séparées gauche/droite avant regroupement lignes → blocs, ordre column-major (aligné PyMuPDF `get_text("dict")`)
- Persistance raw SQLite compatible avec le schéma Python
- Pas de sections, chunks, stat blocks, filtrage, ni comptage de tokens
