# Phase 3 — Audit Engine Design

**Date:** 2026-05-05
**Branch:** feat/audit-engine
**Status:** Approved, ready for implementation

---

## Overview

Phase 3 takes the scraped page data produced by Phase 2 and turns it into a structured `AuditReport` with per-category scores and a list of `AuditIssue` records. Two categories (SEO, Tech) are scored deterministically in pure Python. Three categories (Conversion, Content, Trust) are scored by Claude via structured tool-use calls.

**Done when:** A completed audit job produces an `AuditReport` with an overall score and a populated `AuditIssue` list for a real website.

---

## Key Decisions

- **Homepage only** — All scorers run against the first/root scraped page. Multi-page aggregation is out of scope for Phase 3.
- **Celery chain** — `scrape_website` chains into `run_audit` on success. One POST trigger drives the full scrape → audit flow. The job stays `running` until `run_audit` completes.
- **Structured Python logging** — LLM call metadata (model, tokens, latency, cost, prompt version) is written as JSON log lines. No new DB model.
- **Scorers package** — Five scorer modules under `audits/scorers/`, each with a single clear input (`ScrapedPage`) and output (`CategoryResult`). No Celery or ORM knowledge inside scorers.

---

## File Structure

```
backend/audits/
├── scorers/
│   ├── __init__.py
│   ├── schemas.py          # shared Pydantic models
│   ├── claude_client.py    # retry wrapper + structured JSON logging
│   ├── seo.py              # deterministic SEO scorer
│   ├── tech.py             # deterministic Tech scorer
│   ├── conversion.py       # LLM-judged Conversion scorer
│   ├── content.py          # LLM-judged Content scorer
│   └── trust.py            # LLM-judged Trust scorer
├── tasks.py                # updated scrape_website + new run_audit task
├── serializers.py          # updated: AuditReportSerializer, AuditIssueSerializer
├── views.py                # updated: audit detail + issues list views
└── urls.py                 # updated: new routes
```

---

## Shared Pydantic Schemas (`scorers/schemas.py`)

```python
class ParameterResult(BaseModel):
    key: str        # e.g. "meta_title_length"
    score: int      # 0–10
    rationale: str  # one sentence

class CategoryResult(BaseModel):
    category: str               # "seo" | "conversion" | "content" | "tech" | "trust"
    score: int                  # 0–100
    parameters: list[ParameterResult]
    top_issues: list[str]       # parameter keys with score <= 5
    summary: str                # one sentence
```

Deterministic category score: `round(mean(p.score for p in parameters) * 10)`
LLM category score: returned directly in Claude's tool-use response.

---

## Issue Severity Mapping

Applied by `run_audit` when writing `AuditIssue` rows. Only parameters with score ≤ 6 produce issues.

| Parameter score | Severity   |
|----------------|------------|
| 0–3            | critical   |
| 4–6            | warning    |
| 7–10           | no issue   |

---

## Deterministic Scorers

### SEO (`scorers/seo.py`) — 6 parameters

| Key | Check | Score |
|-----|-------|-------|
| `meta_title` | Exists + 50–60 chars | 10 = exists+in-range, 5 = exists wrong length, 0 = missing |
| `meta_description` | Exists + 150–160 chars | same pattern |
| `h1_tag` | Exactly one H1 | 10 = one, 5 = multiple, 0 = none |
| `image_alts` | All images have alt text | `round(10 * present / total)` if total > 0, else 10 (no images = pass) |
| `internal_links` | ≥ 3 internal links | 10 = ≥3, 5 = 1–2, 0 = none |
| `canonical_tag` | `<link rel="canonical"` in HTML | 10 = present, 0 = absent |

### Tech (`scorers/tech.py`) — 6 parameters

| Key | Check | Score |
|-----|-------|-------|
| `https` | `ScrapedPage.https == True` | 10 or 0 |
| `load_time` | `load_time_ms` | 10 = <2000ms, 5 = 2000–4000ms, 0 = >4000ms |
| `mobile_viewport` | `<meta name="viewport"` in HTML | 10 or 0 |
| `render_blocking_js` | `<script` without `defer`/`async` in `<head>` | 10 = 0 blocking, 5 = 1–2, 0 = 3+ |
| `broken_links` | Any scraped page with `status_code >= 400` across all pages in the job | 10 = none, 5 = 1, 0 = 2+ |
| `cookie_consent` | Common banner patterns (`cookiebot`, `cookie-consent`, `gdpr`) in HTML | 10 = present, 5 = absent |

Note: `broken_links` is the only parameter that reads beyond the homepage — it checks `status_code` across all `ScrapedPage` records for the job.

---

## LLM Scorers

### `claude_client.py`

Single function used by all three LLM scorers:

```python
def score_with_claude(
    category: str,
    prompt: str,
    prompt_version: str,
) -> CategoryResult:
    ...
```

- Uses `claude-sonnet-4-6`
- Forces structured output via `tool_use` with a tool definition matching `CategoryResult`
- Retries up to 3 attempts on failure
- On all 3 failures: returns fallback `CategoryResult` with `score=50`, empty parameters, summary noting the fallback
- Logs every attempt as a JSON line: `model`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `prompt_version`, `attempt`, `success`
- Cost estimate uses hardcoded rates: input $3/M tokens, output $15/M tokens

### Prompt inputs (all three LLM scorers)

Each scorer builds its prompt from:
- `extracted_text` truncated to ~3000 chars
- `meta_title`, `meta_description`, `h1_tags`, `h2_tags`
- Hardcoded rubric string for the category
- `prompt_version` constant defined in the scorer file (e.g. `"conversion-v1"`)

### LLM scorer parameters

**Conversion (`scorers/conversion.py`)** — 5 parameters:
`cta_clarity`, `value_proposition`, `social_proof`, `pricing_transparency`, `form_field_count`

**Content (`scorers/content.py`)** — 5 parameters:
`headline_pain_point`, `benefits_vs_features`, `reading_level`, `brand_voice`, `content_depth`

**Trust (`scorers/trust.py`)** — 5 parameters:
`testimonials`, `about_page`, `contact_info`, `privacy_policy`, `trust_badges`

---

## `run_audit` Celery Task

### Changes to `scrape_website`

On the success path (where it previously set `status='complete'`): keep status as `'running'` and call `run_audit.delay(audit_job_id)` instead.

### `run_audit` flow

```
1. Fetch AuditJob; set status='running' if not already
2. Find homepage ScrapedPage (match `url` on `scheme://netloc` of `business.url`; fallback to first page ordered by `scraped_at`)
3. Fetch all ScrapedPage records for the job (for broken_links check)
4. Run all 5 scorers:
     seo_result    = score_seo(page)
     tech_result   = score_tech(page, all_pages)
     conv_result   = score_conversion(page)
     content_result = score_content(page)
     trust_result  = score_trust(page)
5. Compute weighted overall score:
     overall = round(
         seo_result.score    * 0.20 +
         tech_result.score   * 0.20 +
         conv_result.score   * 0.25 +
         content_result.score * 0.20 +
         trust_result.score  * 0.15
     )
6. Save AuditReport (overall + per-category scores + raw_llm_response as `{"conversion": <CategoryResult dict>, "content": <CategoryResult dict>, "trust": <CategoryResult dict>}`)
7. For each ParameterResult with score <= 6: save AuditIssue
8. Set job.status='complete', job.completed_at=now()
```

Any unhandled exception: set `job.status='failed'`, `job.error_message=str(e)`.

---

## Weights

| Category   | Weight |
|------------|--------|
| SEO        | 20%    |
| Tech       | 20%    |
| Conversion | 25%    |
| Content    | 20%    |
| Trust      | 15%    |

---

## New API Endpoints

```
GET /api/audits/:id/         → AuditReport with nested AuditIssues
GET /api/audits/:id/issues/  → AuditIssue list (filterable by ?category= and ?severity=)
```

`AuditReportSerializer` nests `AuditIssueSerializer` inline.
The existing `GET /api/audits/:id/status/` stays unchanged.

---

## Out of Scope for Phase 3

- RAG retrieval (Phase 4)
- Recommendations (Phase 5)
- Frontend display (Phase 6)
- LLMCallLog DB model (deferred — logs are sufficient for now)
- Multi-page scoring aggregation
