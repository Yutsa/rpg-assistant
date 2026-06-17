# Solo RPG Companion

Solo RPG Companion is an idea for a storytelling app that lets people play tabletop role-playing adventures on their own, guided by an AI game master.

The project is built around a simple problem: many people love tabletop RPGs, but finding a regular group, matching schedules, and keeping a campaign alive can be difficult. Solo role-playing already offers a way around that, but it often requires juggling rulebooks, random tables, notes, and interpretation tools at the same time.

This app imagines a smoother version of that experience.

The player would bring an existing adventure module, then play through it in a text-based conversation with an AI game master. The game master would guide scenes, portray characters, present choices, answer questions, and help resolve what happens next while respecting the spirit and content of the adventure.

The goal is not to replace human game masters or group play. It is to create another way to enjoy RPG material: a personal, flexible, always-available mode for exploring adventures when a full table is not possible.

## Core Idea

The app would help turn a written RPG adventure into a playable solo campaign.

A player could:

- Load an adventure they want to play.
- Create or import a character.
- Explore the story through conversation.
- Make decisions, investigate locations, meet NPCs, and face consequences.
- Keep a persistent record of what has happened.
- Resume the adventure later without losing the thread.

The experience should feel closer to playing with a careful game master than chatting with a generic writing assistant.

## Narrative Memory

A key part of the concept is memory.

The app should remember what the player has discovered, which characters they have met, what choices they made, what dangers remain unresolved, and what parts of the adventure are still hidden.

This matters because solo play depends heavily on continuity. The player should not need to constantly remind the app who they are, where they went, or what clues they already found.

## Session Recaps

One of the most important features is the ability to turn a play session into a written artifact.

After playing, the app could generate different kinds of summaries:

- A concise session log.
- A character journal.
- A dramatic excerpt from a novel.
- A letter, rumor, or newspaper article from inside the game world.
- A campaign chronicle that grows over time.

The idea is that each session leaves behind something enjoyable to read, share, and revisit.

## Intended Experience

The project aims for a tone that is flexible and player-driven.

Some players may want a faithful, rules-aware game master. Others may want a lighter storytelling companion that focuses on mood, pacing, and dramatic consequences. The app should support solo play without making the player feel like they are simply prompting a chatbot.

The ideal experience is:

- Private and self-paced.
- Focused on discovery rather than spoilers.
- Respectful of the original adventure.
- Good at maintaining continuity.
- Able to produce memorable written records of play.

## Why This Exists

Tabletop RPG books are full of stories, places, characters, secrets, and situations that many people never get to play. This project explores a way to make those adventures more accessible without needing a full group at the table.

It is for players who want to experience adventures they own, test scenarios, explore campaign material, or simply enjoy role-playing when scheduling a session is not realistic.

At its heart, Solo RPG Companion is about making solo role-playing easier, richer, and more memorable.

## Campaign Ingestion (dev setup)

The ingestion pipeline has two layers:

- **Raw (deterministic):** PDF → pages, blocks with bbox, sections, chunks. No LLM.
- **Semantic (agent-driven):** External agents submit classifications, entities, and relations via MCP. Validated deterministically in code.

### Monorepo layout

```
packages/
  core/     # rpg-core — models, storage, stat-block utilities
  ingest/   # rpg-ingest — PDF pipeline + CLI (rpg-ingest)
  mcp/      # rpg-mcp — MCP server (rpg-assistant-mcp)
  api/      # rpg-api — REST API (rpg-api)
apps/
  web/      # Angular frontend
migrations/ # Alembic (shared database schema)
tests/      # pytest suite (all packages)
```

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.11+ (uv can install it automatically if missing)
- Docker (optional, only if you use PostgreSQL locally)

### Install

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
```

`uv sync` creates `.venv`, installs locked dependencies (including dev tools), and installs this project in editable mode. Re-run it after pulling changes that touch `uv.lock`.

Run project commands through `uv run` (no manual activation needed), for example `uv run pytest` or `uv run rpg-ingest raw extract ...`.

**Database:** by default the app uses SQLite (`sqlite:///./data/rpg_assistant.db`) — no Docker required. For PostgreSQL (e.g. production or shared dev), set `DATABASE_URL` in `.env` and start Postgres:

```bash
# .env
DATABASE_URL=postgresql://rpg:rpg@localhost:5432/rpg_assistant

docker compose up -d
uv run alembic upgrade head
```

### CLI (large PDFs / batch)

```bash
uv run rpg-ingest raw extract path/to/campaign.pdf --campaign-id camp_my_adventure
uv run rpg-ingest raw status --ingestion-run-id run_xxxxxxxxxxxx
```

### HTTP API

Read-only REST API over the ingested data (campaigns, documents, sections, chunks, stat blocks, PDF page renders):

```bash
uv run rpg-api
```

Server listens on [http://127.0.0.1:8000](http://127.0.0.1:8000). OpenAPI docs at `/docs`.

CORS is enabled for the Angular dev server (`http://localhost:4200` by default). Override with `CORS_ORIGINS` (comma-separated) if needed.

### Frontend (Angular)

The web UI lives in `apps/web/` and proxies API calls to `rpg-api` during development.

**Prerequisites:** Node.js **22.22.3+** (see `apps/web/.nvmrc`) and npm.

```bash
cd apps/web
npm install
npm start
```

Open [http://localhost:4200](http://localhost:4200). Start `uv run rpg-api` in another terminal so the proxy (`/api` → `http://127.0.0.1:8000`) can reach the backend.

**E2E tests (Playwright):**

```bash
cd apps/web
npx playwright install chromium
npm run test:e2e              # integration + acceptance
npm run test:e2e:integration
npm run test:e2e:acceptance
```

Tests seed a deterministic SQLite database (`data/e2e_rpg_assistant.db`) via `scripts/seed_e2e_db.py` and start both the API and Angular dev server automatically.

### MCP server (Cursor / Claude Desktop)

Add `.cursor/mcp.json` (example included) or configure your MCP client:

```json
{
  "mcpServers": {
    "rpg-assistant": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "${workspaceFolder}", "run", "rpg-assistant-mcp"],
      "env": {
        "DATABASE_URL": "sqlite:///./data/rpg_assistant.db"
      },
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

See `AGENTS.md` for the agent workflow (explore chunks, test semantic MVP).

Restart Cursor after editing `.cursor/mcp.json`, then check **Settings → Tools & MCP** that `rpg-assistant` is connected. Tools include `import_pdf`, `list_sections`, `list_chunks`, `get_chunk`, `get_source_excerpt`, `submit_chunk_classifications`, `submit_entities`, `submit_relations`, `validate_semantic_layer`, and `get_semantic_summary`. Resources expose JSON schemas and a reference extraction prompt at `ingestion://schemas/*` and `ingestion://prompts/entity_extraction`.

### Test workflow with an external agent

1. Extract: `rpg-ingest raw extract ...` or MCP `import_pdf` — check `text_coverage_ratio` in status.
2. Explore: `list_sections` → `list_chunks` → `get_chunk` per chapter.
3. Submit: `submit_chunk_classifications`, then `submit_entities` with `source_refs` pointing to real `chunk_id` values.
4. Validate: `validate_semantic_layer` — fix errors and resubmit.
5. Relations: `submit_relations`, then `get_semantic_summary`.

Read `docs/technical-ingestion.md` for the full data model. The exploratory script `packages/ingest/scripts/count_pdf_tokens.py` is unchanged.
