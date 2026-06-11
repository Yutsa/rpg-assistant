# RPG Assistant — Webapp

Interface React pour explorer une campagne importée : sections, chunks, fiches COF2 et vue PDF avec surlignages bbox.

## Prérequis

- Python 3.11+ avec `uv` (backend)
- Node.js 20+ et npm (frontend)
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

Terminal 2 — Vite avec proxy `/api` → `http://127.0.0.1:8000` :

```bash
cd web
npm install
npm run dev
```

Ouvrir [http://localhost:5173](http://localhost:5173).

Le client HTTP utilise par défaut le préfixe `/api` (voir `vite.config.ts`). Variable optionnelle : `VITE_API_BASE`.

## Production locale (un seul processus)

```bash
cd web && npm install && npm run build
uv run rpg-web
```

L'app est servie sur [http://127.0.0.1:8000](http://127.0.0.1:8000) (API + fichiers statiques `web/dist`).

## PDF source introuvable

Si le fichier PDF a été déplacé, l'UI propose un champ de chemin absolu. La valeur est persistée dans `localStorage` sous la clé `rpg-assistant:pdf-path:{documentId}` et transmise en query `pdf_path` aux requêtes de rendu.

Réimporter via la CLI met à jour `source_pdf_path` dans les stats du run raw.

## Tests frontend

```bash
cd web && npm test
```

Test Vitest sur la conversion bbox → viewport (`src/utils/bbox.test.ts`).
