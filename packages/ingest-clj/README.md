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

## Périmètre

- PDFBox `PDFTextStripper` avec `setSortByPosition true`
- Regroupement des `TextPosition` en bandes Y (tolérance 2 pt), puis split par gap horizontal adaptatif entre glyphes voisins
- Pas d'import SQLite, sections, chunks, détection titre/full-width, ni filtrage
