# rpg-ingest-clj

Extraction PDFBox minimale en Clojure : une ligne PDFTextStripper = un bloc, sans heuristiques de layout.

## Prérequis

- Java 21+
- Clojure CLI 1.12+

## Extraction d'une page (JSON)

```bash
cd packages/ingest-clj
clojure -M:ingest raw extract-page --pdf /path/to/document.pdf --page 1
```

Sortie JSON : `page_number`, `width`, `height`, `blocks[]` avec `block_index`, `text`, `bbox`, `metadata`.

Utilisé par l'API `GET /documents/{id}/pages/{n}/extractors-compare` et le viewer de comparaison PyMuPDF / PDFBox dans la webapp.

## Tests

```bash
cd packages/ingest-clj
clojure -M:test
```

## Périmètre

- PDFBox `PDFTextStripper` avec `setSortByPosition true`
- Regroupement minimal des `TextPosition` en lignes (tolérance Y = 2 pt) pour obtenir des bbox affichables
- Pas d'import SQLite, sections, chunks, colonnes, fusion de lignes, ni filtrage
