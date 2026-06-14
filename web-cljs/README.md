# RPG Assistant — front-end ClojureScript (Replicant)

Front-end de l'explorateur de campagne, en **ClojureScript** avec [Replicant](https://replicant.fun/).

## Stack

- **Replicant** — rendu hiccup → DOM, UI en fonctions pures
- **Silk** + **lambdaisland/uri** — routing bidirectionnel ([tutoriel Replicant](https://replicant.fun/tutorials/routing/))
- **`js/fetch`** — appels HTTP JSON ([tutoriel network reads](https://replicant.fun/tutorials/network-reads/))
- **shadow-cljs** — compilation et serveur de dev
- **tools.deps** — gestion des dépendances Clojure

## Prérequis

- Java 11+ (JDK 21 recommandé)
- [Clojure CLI](https://clojure.org/guides/install_clojure)
- Node.js 20+
- Backend FastAPI : `uv run alembic upgrade head`

## Développement (deux processus)

Terminal 1 — API sur le port 8000 :

```bash
uv run rpg-web
```

Terminal 2 — shadow-cljs sur le port 5174 :

```bash
cd web-cljs
npm install
npm run dev
```

Ouvrir [http://127.0.0.1:5174](http://127.0.0.1:5174).

En dev, le client appelle directement `http://127.0.0.1:8000` (CORS activé pour le port 5174).

## Build production

```bash
cd web-cljs
npm install
npm run build
```

Les artefacts sont dans `web-cljs/dist/` (`index.html`, `css/`, `js/compiled/`).

L'API `rpg-web` sert ce dossier sur [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Fonctionnalités

| Vue | Statut |
|-----|--------|
| Liste campagnes | ✅ |
| Documents d'une campagne | ✅ |
| Explorateur (sections/chunks/PDF) | ✅ |
| Fiches stats COF2 | ✅ |
| Navigation mobile (onglets) | ✅ |
| Panneau PDF + surlignage bbox | ✅ |
| Override chemin PDF (`localStorage`) | ✅ |

## Structure

```
web-cljs/
  deps.edn
  shadow-cljs.edn
  public/          # HTML + CSS statiques
  src/
    rpg_assistant_web/
      core.cljs    # point d'entrée, boucle render, routing
      state.cljs   # atom global
      events.cljs  # dispatch Replicant + chargements
      api.cljs     # js/fetch JSON
      router.cljs  # Silk + History API
      views/       # hiccup par écran
      utils/       # bbox, pdf-path
```

## Tests

Tests unitaires ClojureScript (bbox, router) :

```bash
cd web-cljs && npm test
```

Tests d'acceptation Playwright (nécessite `npm run build` dans `web-cljs`) :

```bash
uv run playwright install chromium
uv run python -m pytest tests/acceptance/
```
