# Product Vision

## Overview

The product is a campaign intelligence workspace for tabletop role-playing games.

Its first goal is to help human game masters turn long campaign PDFs into structured, searchable, interactive campaign databases. Its second goal is to use that same structured campaign database as the foundation for an AI game master capable of running solo RPG sessions.

The project should not start as "an AI that replaces the GM." A stronger initial product is a tool that helps game masters prepare, navigate, and run published adventures more efficiently.

Over time, the same underlying campaign model can support solo play, AI-assisted prep, AI co-GM features, and eventually a full AI GM mode.

## Product Thesis

Published RPG campaigns contain a large amount of useful information: locations, NPCs, secrets, clues, factions, timelines, encounters, maps, handouts, and hidden dependencies. However, this information is often spread across hundreds of pages and is difficult to access during actual play.

The product turns a campaign book into a structured and navigable workspace.

The core value is not just summarization. It is making campaign material usable at the table:

- Find relevant information quickly.
- Understand how people, places, clues, and secrets connect.
- Track what players have discovered.
- Prepare sessions faster.
- Avoid accidentally revealing hidden information.
- Keep continuity across a long campaign.

## Phase 1: Human GM Campaign Workspace

Phase 1 focuses on human game masters.

The user imports a campaign PDF they own. The system extracts and organizes the campaign into an interactive database. The GM can then browse, search, annotate, and use that database while preparing or running sessions.

### Core Experience

The GM should be able to:

- Upload a campaign PDF.
- Browse the campaign by chapter, scene, location, NPC, faction, clue, secret, item, and encounter.
- Search the campaign using natural language.
- Open source references back to the original PDF page.
- Open the original PDF directly at the relevant page or highlighted source section.
- View player-safe descriptions separately from GM-only information.
- Track which clues, secrets, locations, and NPCs have been revealed to players.
- Add private notes and session notes.
- Prepare a session by selecting relevant scenes and entities.
- Quickly answer questions such as:
  - Where does this NPC appear?
  - What does this clue point to?
  - Which secrets are connected to this location?
  - What do the players currently know?
  - What should not be revealed yet?

### MVP Features

An initial MVP could include:

- Text-based PDF upload and text extraction.
- Rejection of scanned or image-only PDFs.
- Campaign outline by chapters and sections.
- Searchable source chunks.
- Extracted index of locations, NPCs, factions, secrets, clues, and items.
- Detail pages for each extracted entity.
- Source page references in the original PDF.
- Side-by-side display of extracted data and original PDF source page.
- Manual correction of extracted entities.
- Basic session notes.
- Reveal tracking for player-known facts.

### Strong Differentiators

The product should focus on campaign usability, not generic document chat.

Important differentiators:

- Spoiler-aware information model.
- Source-backed extracted facts.
- Direct verification of extracted facts in the user's original PDF.
- Separation between player-visible and GM-only information.
- Relationship graph between locations, NPCs, clues, and secrets.
- Session mode for live play.
- Campaign state tracking over time.

## Phase 2: AI GM and Solo Play

Phase 2 uses the structured campaign database as the knowledge layer for an AI game master.

The AI GM should not receive the full PDF as context. Instead, it should receive focused scene packets and retrieve only the information relevant to the current moment of play.

### Core Experience

The player can play a campaign in solo mode through a text-based conversation with an AI GM.

The AI GM should:

- Present scenes and descriptions.
- Portray NPCs.
- Ask for player decisions.
- Resolve consequences.
- Respect the campaign's hidden information.
- Avoid spoilers.
- Use the campaign database as its source of truth.
- Track what the player has discovered.
- Produce session recaps and in-world written artifacts.

### AI GM Extensions

Before a full solo GM mode, the same system could support smaller AI features for human GMs:

- Ask the campaign: "What does this NPC know?"
- Generate a session recap from notes.
- Suggest likely consequences of player actions.
- Prepare a scene briefing.
- Produce player-safe summaries.
- Generate in-world rumors, letters, or newspaper articles based on actual campaign events.

These features reduce risk because the human GM remains in control while the system proves the quality of the campaign knowledge base.

## Roadmap

### Stage 1: Campaign Bible

Turn a campaign PDF into a searchable structured campaign bible.

Primary users: GMs preparing a campaign.

### Stage 2: GM Workspace

Add session preparation, annotations, reveal tracking, and live navigation.

Primary users: GMs running a campaign.

### Stage 3: AI Prep Assistant

Add AI features that help a GM query, summarize, and prepare material.

Primary users: GMs who want faster preparation without giving up control.

### Stage 4: AI Co-GM

Add optional support during play: reminders, scene packets, continuity checks, recap generation, and consequence suggestions.

Primary users: GMs running complex campaigns.

### Stage 5: Solo AI GM

Use the same campaign database and runtime state tracking to power solo play with an AI GM.

Primary users: players who want to experience campaigns without scheduling a full group.

## Product Principles

- The source material remains the source of truth.
- Extracted information must be traceable to the original PDF.
- Source references should be viewable in the original PDF whenever possible.
- The system must separate player-known information from GM-only information.
- The product should help human GMs before trying to replace them.
- The AI GM should consume structured campaign context, not the entire campaign book.
- Manual correction and review should be treated as first-class features.
- Campaign continuity matters more than flashy generation.

## PDF Support Scope

The first version should support text-based PDFs only.

Scanned or image-only PDFs should be rejected during import with a clear message. OCR is intentionally out of scope for the initial product because it adds cost, complexity, uncertain quality, and harder source alignment.

This constraint makes source verification more reliable: extracted entities can point back to the original PDF page, and later to precise text regions on that page.

## Legal and Content Boundaries

The product should assume users bring their own legally owned campaign PDFs.

The system should avoid becoming a repository of redistributed commercial content. It should also avoid exports that effectively replace the original module.

Important boundaries to consider:

- No public sharing of extracted commercial campaigns by default.
- No marketplace of unlicensed extracted modules.
- Source references should point to the user's own document.
- Source previews should support play and verification, not become a replacement for the full book.
- Generated summaries should support play, not replace ownership of the source book.

## Long-Term Vision

The long-term vision is a campaign intelligence layer for tabletop RPGs.

The same structured campaign model can support:

- Human GM prep.
- Live campaign navigation.
- Player knowledge tracking.
- AI-assisted session recaps.
- AI co-GM support.
- Solo RPG play.
- Campaign continuity across many sessions.

The AI GM is not the starting point. It is the most ambitious application of a deeper product: making RPG campaigns machine-readable, navigable, and playable.
