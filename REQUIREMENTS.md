# AI Business Operating System — Claude Code Build Requirements

## Project Overview

Build an AI-powered Business Operating System that scrapes a company's website, audits it across multiple dimensions, uses RAG to ground recommendations in best practices, runs a decision engine to prioritize issues, and presents findings on a dashboard. The user sees scores, issues, and prioritized recommendations — no content generation, no automation integrations.

**Core loop:** Scrape → Audit → Decide → Display

---

## What to build (and what to skip)

### IN SCOPE
- Website scraping and data ingestion
- AI audit engine (structured scoring across 5 categories)
- RAG knowledge system (pgvector + embeddings)
- Decision engine (rules + LLM reasoning)
- Dashboard (scores, issues, recommendations, history)
- REST API (Django + DRF)
- Frontend (Next.js)

### OUT OF SCOPE (explicitly skip these)
- User authentication / multi-tenant workspaces
- Content generation (landing page copy, ad copy, email sequences)
- Workflow automation (n8n, Pipedream)
- CRM integrations / webhooks

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Django + Django REST Framework |
| Frontend | Next.js (App Router) |
| Database | PostgreSQL |
| Vector DB | pgvector (via `pgvector` Django integration) |
| AI | Anthropic Claude API (primary) + OpenAI for embeddings |
| Queue | Redis + Celery |
| Scraping | Playwright + BeautifulSoup4 |
| Deployment | Docker Compose |

---

## CLAUDE.md Instruction

> **First thing Claude Code must do:** Create a `CLAUDE.md` file in the project root. This file is the source of truth for the project and must be kept up to date throughout development. It should contain:
> - Project overview (one paragraph)
> - Tech stack (with versions once known)
> - Folder structure (updated as new dirs are added)
> - Environment variables required (names only, no values)
> - How to run the project locally
> - Phase completion status (checklist, updated after each phase)
> - Key architectural decisions and why they were made
> - Any known issues or TODOs
>
> Update `CLAUDE.md` at the end of every phase before wrapping up.

---

## Data Models

### Business
```
id, name, url, industry_type, created_at, updated_at
```

### AuditJob
```
id, business_id, status (pending/running/complete/failed),
triggered_at, completed_at, error_message
```

### AuditReport
```
id, audit_job_id, overall_score (0-100),
seo_score, conversion_score, content_score, tech_score, trust_score,
raw_llm_response (JSON), created_at
```

### AuditIssue
```
id, report_id, category (seo/conversion/content/tech/trust),
severity (critical/warning/info), title, description,
parameter_key, score (0-10), created_at
```

### Recommendation
```
id, report_id, issue_id (FK, nullable),
priority_score (float), effort (low/medium/high),
impact (low/medium/high), title, rationale, created_at
```

### KnowledgeDoc
```
id, title, category, content (text), embedding (vector),
source, created_at
```

### ScrapedPage
```
id, business_id, audit_job_id, url, html_content,
extracted_text, meta_title, meta_description,
h1_tags (JSON), h2_tags (JSON), internal_links (JSON),
load_time_ms, https, status_code, scraped_at
```

---

## Audit Engine — Scoring Categories & Parameters

Each category scores 0–100. Overall score = weighted average.

### 1. SEO (weight: 20%)
Deterministic checks:
- Meta title exists and is 50–60 chars
- Meta description exists and is 150–160 chars
- H1 tag exists (exactly one)
- Image alt texts present
- Internal linking structure
- Canonical tag present

### 2. Conversion (weight: 25%)
LLM-judged:
- CTA clarity and specificity above the fold
- Value proposition clarity (who, what, why in one sentence)
- Social proof presence (testimonials, logos, reviews)
- Pricing transparency
- Form field count (fewer = better)

### 3. Content (weight: 20%)
LLM-judged:
- Headline addresses a real pain point
- Benefits vs features ratio
- Reading level appropriateness
- Brand voice consistency across pages
- Content depth / word count adequacy

### 4. Tech / Performance (weight: 20%)
Deterministic + Playwright:
- HTTPS enforced
- Page load time (Playwright timing)
- Mobile viewport meta tag
- Render-blocking JS count
- Broken internal links (404s)
- Cookie consent banner

### 5. Trust (weight: 15%)
LLM-judged:
- Testimonials or case studies exist
- Team / About page present
- Contact information visible
- Privacy policy + ToS links
- Certifications or trust badges

---

## System Prompt Design (Audit Engine)

Each LLM-judged category gets its own prompt call with a rubric. Claude must return structured JSON only. Example schema per category:

```json
{
  "category": "conversion",
  "score": 62,
  "parameters": [
    {
      "key": "cta_clarity",
      "score": 4,
      "rationale": "CTA says 'Submit' with no benefit language, placed below the fold"
    }
  ],
  "top_issues": ["weak_cta", "no_social_proof"],
  "summary": "One sentence category summary"
}
```

Use `tool_use` / structured output mode — never parse free text.

---

## RAG Knowledge System

### Knowledge Base Seeding
Pre-populate with markdown documents covering:
- CTA copywriting best practices
- Value proposition frameworks (PAS, AIDA)
- SEO on-page checklist
- Core Web Vitals guidance
- Trust signal best practices
- Conversion rate optimization research

### Retrieval Flow
1. Audit identifies an issue (e.g. weak CTA)
2. Embed the issue description using OpenAI `text-embedding-3-small`
3. Run cosine similarity search against `KnowledgeDoc` embeddings in pgvector
4. Retrieve top 3 matching docs
5. Inject into decision engine prompt as context

### Embedding Pipeline
- Embed all KnowledgeDocs at seed time (management command)
- Re-embed if document content changes
- Store embedding as `vector(1536)` in pgvector

---

## Decision Engine

Takes audit output + RAG context → produces prioritized `Recommendation` list.

### Step 1: Rules engine (deterministic)
Apply priority overrides:
- Any `critical` severity issue → always rank first
- Broken links or HTTPS missing → always surface as blockers
- Score below 40 in any category → flag as urgent

### Step 2: LLM reasoning pass
Feed the ranked issues + RAG-retrieved docs to Claude with prompt:
> "Given these audit issues and best-practice context, produce a prioritized recommendation list. For each recommendation, assign effort (low/medium/high), impact (low/medium/high), and write a one-sentence rationale grounded in the provided context."

Return structured JSON list of Recommendation objects.

---

## API Endpoints (Django REST Framework)

```
POST   /api/businesses/                  # Add a business (name + URL + industry)
GET    /api/businesses/                  # List all businesses
GET    /api/businesses/:id/              # Business detail

POST   /api/businesses/:id/audit/        # Trigger a new audit (queues Celery job)
GET    /api/businesses/:id/audits/       # Audit history for a business
GET    /api/audits/:id/                  # Full audit report detail
GET    /api/audits/:id/issues/           # Issues for an audit
GET    /api/audits/:id/recommendations/  # Recommendations for an audit

GET    /api/audits/:id/status/           # Poll job status (pending/running/complete)

POST   /api/knowledge/seed/              # Trigger knowledge base seeding (admin)
```

---

## Frontend — Next.js Pages

```
/                          # Home — list businesses, add new business form
/business/:id              # Business overview — latest audit score, trigger new audit
/business/:id/audit/:auditId  # Full audit report
  - Overall score (large, prominent)
  - Category score breakdown (5 cards)
  - Issues list (filterable by category + severity)
  - Recommendations list (sorted by priority)
/business/:id/history      # Past audits — score trend over time
```

### Dashboard UI requirements
- Overall score displayed as a large number with a color band (0–40 red, 41–70 amber, 71–100 green)
- 5 category score cards with score, weight label, and a short status line
- Issues table: severity badge, category tag, parameter name, rationale text
- Recommendations list: priority rank, effort/impact badge, title, rationale
- Audit status polling (show spinner while job is running)
- Score trend chart on history page (line chart, one point per audit)

---

## Development Phases & Branch Strategy

Work in phases. Each phase = one GitHub branch. At the end of each phase:
1. Update `CLAUDE.md` with what was completed
2. Confirm all endpoints/components work
3. Commit and push the branch
4. Prompt the developer to open a PR and merge before starting the next phase

---

### Phase 1 — `feat/foundation`
**Goal:** Project skeleton, DB, Docker, basic models

- Django project setup with DRF
- Next.js project setup (App Router)
- Docker Compose: Django + Postgres + Redis + Next.js
- pgvector extension enabled in Postgres
- All data models created and migrated
- Django admin registered for all models
- Health check endpoint `GET /api/health/`
- `CLAUDE.md` created and populated

**Done when:** `docker compose up` runs all services, migrations apply cleanly, admin is accessible.

---

### Phase 2 — `feat/scraper`
**Goal:** Given a URL, produce structured page data in the DB

- Celery worker configured with Redis broker
- `scrape_website` Celery task:
  - Playwright: load page, capture load time, screenshot
  - BeautifulSoup: extract text, headings, meta tags, links, alt texts
  - HTTP checks: HTTPS, status codes, follow internal links (max 5 pages)
  - Save `ScrapedPage` records per URL
- `AuditJob` status updated (pending → running → complete/failed)
- `POST /api/businesses/:id/audit/` triggers the job
- `GET /api/audits/:id/status/` returns current job status

**Done when:** Triggering an audit on a real URL produces populated `ScrapedPage` records.

---

### Phase 3 — `feat/audit-engine`
**Goal:** Scraped data → structured AuditReport with scores and issues

- Deterministic scorer for SEO and Tech parameters (pure Python, no LLM)
- LLM scorer for Conversion, Content, Trust using Claude API structured output
- Each category gets its own prompt with rubric definitions
- Retry logic for failed LLM calls (max 3 attempts, simplified fallback prompt)
- `AuditReport` and `AuditIssue` records saved after scoring
- Log every LLM call: model, tokens, latency, cost estimate, prompt version
- `GET /api/audits/:id/` returns full report with issues

**Done when:** A completed audit job produces a report with an overall score and issue list for a real website.

---

### Phase 4 — `feat/rag`
**Goal:** Knowledge base seeding + retrieval working

- pgvector Django integration set up (`django-pgvector` or raw SQL)
- `KnowledgeDoc` model with `vector(1536)` embedding field
- Seed management command: `python manage.py seed_knowledge`
  - Loads markdown files from `/knowledge_base/` directory
  - Embeds each using OpenAI `text-embedding-3-small`
  - Saves to DB
- Retrieval function: given an issue description string, return top 3 docs by cosine similarity
- Unit test: retrieval returns relevant docs for sample issue strings

**Done when:** Seeding runs without error, retrieval returns sensible results for test queries.

---

### Phase 5 — `feat/decision-engine`
**Goal:** Issues + RAG context → prioritized Recommendation list

- Rules engine: apply severity/score-based priority overrides
- RAG retrieval called per issue to fetch relevant docs
- LLM reasoning pass: structured prompt → ranked Recommendation JSON
- `Recommendation` records saved to DB
- `GET /api/audits/:id/recommendations/` returns sorted list

**Done when:** A completed audit produces a prioritized recommendation list with rationale grounded in knowledge base content.

---

### Phase 6 — `feat/dashboard`
**Goal:** Full working frontend connected to real API

- Business list page + add business form
- Trigger audit button with polling for job status
- Full audit report page:
  - Overall score with color band
  - 5 category score cards
  - Issues table (filterable)
  - Recommendations list
- Audit history page with score trend chart
- Loading states and error handling throughout
- `CLAUDE.md` updated with final project state

**Done when:** A non-technical user can add a website, trigger an audit, and read their results without touching the terminal.

---

## Environment Variables Required

```
# Django
DJANGO_SECRET_KEY=
DATABASE_URL=
REDIS_URL=
ALLOWED_HOSTS=

# AI
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Celery
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
```

---

## Additional Instructions for Claude Code

- Use `pydantic` models for all LLM response validation — never parse raw text
- Wrap every LLM call in try/except with a logged fallback
- Seed script must be idempotent (safe to run multiple times)
- All Celery tasks must handle failure gracefully and update `AuditJob.status` to `failed` with an error message
- Use environment variables for all secrets — no hardcoded keys anywhere
- At the start of each phase, read `CLAUDE.md` to understand the current project state before writing any code
- At the end of each phase, update `CLAUDE.md` before finishing