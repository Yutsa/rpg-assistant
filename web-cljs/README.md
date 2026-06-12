# RPG Assistant — front-end ClojureScript (Replicant)

Branche expérimentale : rewrite du front-end React (`web/`) en **ClojureScript** avec [Replicant](https://replicant.fun/).

Le front React existant reste la référence fonctionnelle ; ce dossier cohabite en parallèle le temps de la migration.

## Stack

- **Replicant** — rendu hiccup → DOM, UI en fonctions pures
- **shadow-cljs** — compilation et serveur de dev
- **tools.deps** — gestion des dépendances Clojure

## Prérequis

- Java 11+ (JDK 21 recommandé)
- [Clojure CLI](https://clojure.org/guides/install_clojure)
- Node.js 20+
- Backend FastAPI migré : `uv run alembic upgrade head`

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

## État de la migration

| Vue React | Statut cljs |
|-----------|-------------|
| Liste campagnes | ✅ squelette fonctionnel |
| Documents d'une campagne | 🔲 placeholder |
| Explorateur (sections/chunks/PDF) | 🔲 placeholder |
| Fiches stats COF2 | 🔲 placeholder |

## Structure

```
web-cljs/
  deps.edn
  shadow-cljs.edn
  public/          # HTML + CSS statiques
  src/
    rpg_assistant_web/
      core.cljs    # point d'entrée, boucle render
      state.cljs   # atom global
      events.cljs  # dispatch Replicant
      api.cljs     # fetch JSON
      routes.cljs  # routing History API
      views/       # hiccup par écran
```

## Tests

```bash
cd web-cljs && npm test
```

(Tests cljs à ajouter au fil de la migration.)
