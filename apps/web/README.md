# Web

Angular 22 application for browsing ingested RPG campaigns. Lives in `apps/web/` within the monorepo.

**Prerequisites:** Node.js **22.22.3+** (see `.nvmrc`) and npm.

## Development server

```bash
npm install
npm start
```

Open [http://localhost:4200/](http://localhost:4200/). API calls are proxied to `rpg-api` via `proxy.conf.json`.

## Build

```bash
npm run build
```

Artifacts are written to `dist/web`.

## Unit tests

```bash
npm test
```

## End-to-end tests

Requires a seeded database (`scripts/seed_e2e_db.py` from the repo root) and a running API:

```bash
npm run test:e2e
npm run test:e2e:integration
npm run test:e2e:acceptance
```

## Code scaffolding

```bash
ng generate component component-name
```

See the [Angular CLI documentation](https://angular.dev/tools/cli).
