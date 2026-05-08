# AI Business Operating System

## Project Overview
An AI-powered Business Operating System that scrapes a company's website, audits it across five dimensions (SEO, Conversion, Content, Tech, Trust), uses RAG to ground recommendations in best practices, runs a decision engine to prioritize issues, and presents findings on a dashboard.

## Tech Stack
- Backend: Django 4.2, Django REST Framework 3.14, Python 3.11
- Frontend: Next.js 14 (App Router), TypeScript
- Database: PostgreSQL 15 + pgvector
- Queue: Redis 7 + Celery 5.3
- Scraping: Playwright + BeautifulSoup4 (Phase 2)
- AI: Anthropic Claude API + OpenAI embeddings (Phase 3+)
- Deployment: Docker Compose

## Folder Structure
```
ai-business-audit/
├── CLAUDE.md
├── REQUIREMENTS.md
├── .env.example
├── docker-compose.yml
├── knowledge_base/        # Markdown best-practice docs for RAG seeding
├── backend/          # Django project
│   ├── config/       # settings, urls, wsgi, asgi, celery
│   ├── core/         # health check endpoint
│   └── audits/       # all data models, business logic
│       ├── scorers/      # audit scoring engine
│       │   ├── schemas.py        # shared Pydantic models
│       │   ├── claude_client.py  # Claude API wrapper with retry + logging
│       │   └── seo.py / tech.py / conversion.py / content.py / trust.py
│       ├── rag/          # RAG knowledge retrieval
│       │   ├── openai_client.py  # embed_text() via OpenAI text-embedding-3-small
│       │   └── retrieval.py      # retrieve_similar_docs() via pgvector CosineDistance
│       ├── decision/     # Decision engine
│       │   ├── rules.py          # apply_priority_rules() — deterministic tier sorter
│       │   ├── claude_client.py  # generate_recommendations_with_claude() — LLM reasoning
│       │   └── schemas.py        # RecommendationResult Pydantic model
│       ├── management/
│       │   └── commands/
│       │       └── seed_knowledge.py  # seed_knowledge_base() + Django Command
│       ├── scraper.py    # pure page extraction logic (no Celery/DB)
│       ├── tasks.py      # scrape_website + run_audit Celery tasks
│       ├── serializers.py
│       └── views.py
└── frontend/         # Next.js app (App Router)
    └── src/app/
```

## Environment Variables
See `.env.example` for all required variables. Never commit `.env`.

## How to Run Locally
```bash
cp .env.example .env   # fill in real API key values
docker compose up --build
```
- Django API: http://localhost:8000
- Django Admin: http://localhost:8000/admin
- Next.js: http://localhost:3000
- Health check: http://localhost:8000/api/health/

Create a Django superuser:
```bash
docker compose exec backend python manage.py createsuperuser
```

## Phase Completion Status
- [x] Phase 1 — Foundation (skeleton, models, Docker, health check)
- [x] Phase 2 — Scraper (Celery task, Playwright + BS4, 5-page crawl, REST endpoints)
- [x] Phase 3 — Audit Engine (deterministic + LLM scoring, run_audit task, report + issues API)
- [x] Phase 4 — RAG Knowledge System
- [x] Phase 5 — Decision Engine
- [ ] Phase 6 — Dashboard

## Key Architectural Decisions
- **pgvector in Postgres** — keeps vector search co-located with relational data, avoids a separate vector DB service; extension enabled via Django migration
- **Celery + Redis** — decouples long-running scrape/audit jobs from the HTTP request cycle; worker defined in Docker Compose from Phase 1
- **Separate Django apps** — `core` for infrastructure (health check), `audits` for all domain models and business logic
- **django-environ** — all secrets via environment variables, 12-factor compliant; `.env` file mounted read-only into containers
- **scorers/ package** — five independent scorer modules (SEO, Tech deterministic; Conversion, Content, Trust via Claude); each takes a ScrapedPage and returns a Pydantic CategoryResult with no Celery or ORM knowledge
- **claude_client.py** — single entry point for all Claude API calls; retries up to 3 times, logs every attempt as a JSON line (model, tokens, latency, cost_usd, prompt_version)
- **Celery chain** — scrape_website chains into run_audit on success; job stays 'running' through both tasks, set to 'complete' only after auditing finishes
- **audits/rag/ sub-package** — mirrors scorers/ pattern; openai_client.py wraps the OpenAI SDK for embeddings, retrieval.py runs cosine similarity via pgvector CosineDistance annotation; each has one clear responsibility and no Celery/ORM coupling
- **Sync seed endpoint** — POST /api/knowledge/seed/ runs synchronously; seeding ~6 docs takes <5s, so Celery overhead is not justified for a one-time admin operation
- **YAML frontmatter in markdown** — each knowledge_base/*.md file carries title/category/source metadata parsed with python-frontmatter; self-contained, standard format
- **Idempotent seeding** — seed_knowledge_base() skips any KnowledgeDoc whose title already exists; safe to run multiple times; accepts an optional directory parameter for testability
- **decision/ sub-package** — mirrors scorers/ and rag/ pattern; rules.py handles deterministic priority tiering (critical → blocker, low category score → blocker), claude_client.py makes a single LLM call with all ranked issues + per-issue RAG context; generate_recommendations Celery task chains from run_audit via .delay() — failure is logged but does not flip job status since the audit itself is already complete

## Known Issues / TODOs
- Phase 1 only: ANTHROPIC_API_KEY and OPENAI_API_KEY are placeholder values — fill in before Phase 3
- Phase 2: scrape_website runs Playwright in a ThreadPoolExecutor to avoid Django's SynchronousOnlyOperation; all ORM writes happen after the thread exits
