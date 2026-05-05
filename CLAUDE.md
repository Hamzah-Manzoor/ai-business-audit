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
├── backend/          # Django project
│   ├── config/       # settings, urls, wsgi, asgi, celery
│   ├── core/         # health check endpoint
│   └── audits/       # all data models, business logic
│       ├── scraper.py    # pure page extraction logic (no Celery/DB)
│       ├── tasks.py      # scrape_website Celery task
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
- [ ] Phase 3 — Audit Engine
- [ ] Phase 4 — RAG Knowledge System
- [ ] Phase 5 — Decision Engine
- [ ] Phase 6 — Dashboard

## Key Architectural Decisions
- **pgvector in Postgres** — keeps vector search co-located with relational data, avoids a separate vector DB service; extension enabled via Django migration
- **Celery + Redis** — decouples long-running scrape/audit jobs from the HTTP request cycle; worker defined in Docker Compose from Phase 1
- **Separate Django apps** — `core` for infrastructure (health check), `audits` for all domain models and business logic
- **django-environ** — all secrets via environment variables, 12-factor compliant; `.env` file mounted read-only into containers

## Known Issues / TODOs
- Phase 1 only: ANTHROPIC_API_KEY and OPENAI_API_KEY are placeholder values — fill in before Phase 3
- Phase 2: scrape_website runs Playwright in a ThreadPoolExecutor to avoid Django's SynchronousOnlyOperation; all ORM writes happen after the thread exits
