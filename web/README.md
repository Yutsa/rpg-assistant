# RPG Assistant — Webapp

Interface ClojureScript (UIx + si-frame) pour explorer une campagne importée : sections, chunks, fiches COF2 et vue PDF avec surlignages bbox.

## Prérequis

- Python 3.11+ avec `uv` (backend)
- Node.js 20+, npm, Clojure CLI (frontend)
- Base migrée : `uv run alembic upgrade head`
- Au moins un import raw, par ex. campagne `momie` :

```bash
uv run rpg-ingest raw extract <fichier.pdf> --campaign-id momie --game-system cof2
```

## Développement (deux processus)

Terminal 1 — API FastAPI sur le port 8000 :

```bash
uv run rpg-web
```

Terminal 2 — shadow-cljs avec proxy `/api` → `http://127.0.0.1:8000` :

```bash
cd web
npm install
npm run dev
```

Ouvrir [http://localhost:5173](http://localhost:5173).

En dev, le client HTTP utilise le préfixe `/api` (proxy shadow-cljs). En build release, les appels sont relatifs à la racine (même origine que `rpg-web`).

## Production locale (un seul processus)

```bash
cd web && npm install && npm run build
uv run rpg-web
```

L'app est servie sur [http://127.0.0.1:8000](http://127.0.0.1:8000) (API + fichiers statiques `web/dist`).

## PDF source introuvable

Si le fichier PDF a été déplacé, l'UI propose un champ de chemin absolu. La valeur est persistée dans `localStorage` sous la clé `rpg-assistant:pdf-path:{documentId}` et transmise en query `pdf_path` aux requêtes de rendu.

Réimporter via la CLI met à jour `source_pdf_path` dans les stats du run raw.

## Tests d'acceptation (Playwright)

```bash
cd web
npm run build
npm run test:e2e:install   # une fois par machine
npm run test:e2e
```

Le serveur de test (`tests/e2e/serve.py`) charge des données en mémoire et sert le build statique sur le port 8765.

### Captures d'écran (régression visuelle)

Les snapshots Playwright sont versionnés dans `web/e2e/screenshots/` :

```bash
cd web
npm run build
npm run test:e2e:screenshots          # compare aux références
npm run test:e2e:screenshots:update   # régénère les PNG après changement UI
```

Vues couvertes : campagnes, documents, explorateur, chunks, panneau PDF, fiches COF2.

## Stack frontend

- [UIx](https://github.com/pitch-io/uix) — React en ClojureScript
- [si-frame](https://github.com/metosin/si-frame) — état global (panneau PDF)
- shadow-cljs — compilation et dev server
- react-router-dom v6 — routage
