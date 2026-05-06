# Phase 4 — RAG Knowledge System Design

**Date:** 2026-05-05
**Branch:** feat/rag
**Status:** Approved

---

## Overview

Add a RAG (Retrieval-Augmented Generation) knowledge base to the audit system. Given an audit issue description, the system retrieves the top 3 most relevant best-practice documents via cosine similarity search (pgvector). This context will be fed into the decision engine in Phase 5.

---

## Folder Structure

```
ai-business-audit/
├── knowledge_base/                  # Markdown source files
│   ├── cta_copywriting.md
│   ├── value_proposition_frameworks.md
│   ├── seo_onpage_checklist.md
│   ├── core_web_vitals.md
│   ├── trust_signals.md
│   └── cro_research.md
└── backend/
    └── audits/
        ├── rag/                     # New sub-package (mirrors scorers/ pattern)
        │   ├── __init__.py
        │   ├── openai_client.py
        │   └── retrieval.py
        └── management/
            └── commands/
                └── seed_knowledge.py
```

No new Django app or model migrations required — `KnowledgeDoc` (with `VectorField(dimensions=1536)`) is already defined and migrated.

---

## Components

### `audits/rag/openai_client.py`

Thin wrapper around the OpenAI SDK.

- **Function:** `embed_text(text: str) -> list[float]`
- Uses model `text-embedding-3-small`, returns a 1536-dim vector
- Reads `OPENAI_API_KEY` from environment
- Raises `EmbeddingError` (custom exception) on failure — no silent fallback, no retries
- Rationale: seeding is a manual admin operation; a clear failure is better than a silently null embedding

### `audits/rag/retrieval.py`

Cosine similarity search via pgvector.

- **Function:** `retrieve_similar_docs(issue_description: str, top_k: int = 3) -> list[KnowledgeDoc]`
- Embeds the query string via `embed_text`
- Queries pgvector using cosine distance operator (`<=>`)
- Excludes docs where `embedding IS NULL`
- Returns docs ordered by relevance (closest first)
- Raises on embedding failure — caller decides how to handle

### `seed_knowledge` management command

Located at `audits/management/commands/seed_knowledge.py`.

1. Scans all `*.md` files in `/knowledge_base/`
2. Parses YAML frontmatter for `title`, `category`, `source`; body is the content
3. For each doc: if a `KnowledgeDoc` with the same `title` already exists → skip (idempotent)
4. Otherwise: calls `embed_text(content)`, saves `KnowledgeDoc` to DB
5. Catches `EmbeddingError` per document — logs and continues, does not abort
6. Prints summary: `X created, Y skipped`

### `POST /api/knowledge/seed/` endpoint

- Calls the same seeding logic as the management command via a shared helper function (no code duplication)
- Synchronous — runs in the request/response cycle (~5 seconds for 6 docs)
- Returns `{"created": N, "skipped": N}`
- Lives in existing `audits/views.py` and `audits/urls.py`

---

## Knowledge Base Documents

Six markdown files, each with YAML frontmatter:

```markdown
---
title: CTA Copywriting Best Practices
category: conversion
source: internal
---
# Content...
```

Topics:
1. `cta_copywriting.md` — category: conversion
2. `value_proposition_frameworks.md` — category: conversion
3. `seo_onpage_checklist.md` — category: seo
4. `core_web_vitals.md` — category: tech
5. `trust_signals.md` — category: trust
6. `cro_research.md` — category: conversion

---

## Error Handling

| Location | Failure | Behaviour |
|---|---|---|
| `openai_client.py` | OpenAI API call fails | Raise `EmbeddingError` |
| `seed_knowledge` command | `EmbeddingError` for one doc | Log, skip that doc, continue |
| `retrieve_similar_docs` | Embedding fails | Raise — caller handles |
| Seed endpoint | Any exception | Return 500 with error message |

---

## Testing

File: `audits/tests/test_rag.py`

| Test | What it checks |
|---|---|
| `test_retrieve_returns_top_3` | Seeds 5 docs with known vectors, mocks `embed_text` to return a nearby vector, asserts correct 3 returned in order |
| `test_retrieve_skips_null_embeddings` | Docs with `embedding=None` excluded from results |
| `test_seed_command_is_idempotent` | Running seed logic twice produces no duplicate `KnowledgeDoc` rows |

All OpenAI calls mocked via `unittest.mock.patch` — no real API calls in tests.

---

## Key Decisions

- **Sync seed endpoint** — seeding ~6 docs takes <5 seconds; async overhead is not justified for a one-time admin operation
- **YAML frontmatter** — standard format, self-contained, parsed with `python-frontmatter`
- **`audits/rag/` sub-package** — mirrors existing `audits/scorers/` pattern; consistent structure without the migration cost of a new Django app
- **No retries in `openai_client.py`** — seeding is operator-triggered; a clear error is preferable to silent partial state
