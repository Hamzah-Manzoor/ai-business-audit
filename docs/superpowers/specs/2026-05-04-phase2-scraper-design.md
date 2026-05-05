# Phase 2 — Scraper Design

**Date:** 2026-05-04  
**Branch:** `feat/scraper` (from `main`)  
**Status:** Approved

---

## Goal

Given a business URL, produce populated `ScrapedPage` records in the database for up to 5 pages of that website. Trigger via REST API; track progress via `AuditJob` status.

---

## Decisions Made

| Decision | Choice | Reason |
|---|---|---|
| Screenshots | Skipped | Not consumed until Phase 6; adds storage complexity with no Phase 2 benefit |
| Playwright location | Inside existing `backend` Docker image | Simpler than a separate scraper service; 5-page scale doesn't justify inter-service complexity |
| Page discovery | Sitemap.xml first, fallback to first 4 homepage links | Sitemap gives auditable pages; fallback handles sites without one |
| Image alts | Add `image_alts` JSON field + migration now | Scraping is the right place to extract this; Phase 3 SEO scorer needs it |
| Task structure | Single Celery task, per-page error isolation | Resilient to individual page failures without Celery chord complexity |

---

## Architecture

### New Files
- `backend/audits/tasks.py` — `scrape_website` Celery task
- `backend/audits/serializers.py` — DRF serializers
- `backend/audits/views.py` — API views
- `backend/audits/migrations/0003_scrapedpage_image_alts.py` — adds `image_alts` field

### Modified Files
- `backend/audits/urls.py` — endpoint routing
- `backend/config/urls.py` — include audits URLs under `/api/`
- `backend/requirements.txt` — add `playwright`, `beautifulsoup4`, `lxml`
- `backend/Dockerfile` — install Playwright Chromium after pip install

---

## API Endpoints

```
POST /api/businesses/                  → create a business
GET  /api/businesses/                  → list all businesses
GET  /api/businesses/:id/              → business detail
POST /api/businesses/:id/audit/        → trigger scrape job (queues Celery task)
GET  /api/audits/:id/status/           → poll job status
```

`POST /api/businesses/:id/audit/` response:
```json
{"audit_job_id": 7, "status": "pending"}
```

`GET /api/audits/:id/status/` response:
```json
{"id": 7, "status": "running", "triggered_at": "...", "completed_at": null, "error_message": ""}
```

---

## Celery Task: `scrape_website(audit_job_id)`

### Step 1 — Mark running
Set `AuditJob.status = "running"`.

### Step 2 — Discover URLs
1. Fetch `<root_url>/sitemap.xml` using `requests`.
2. If found and parseable: extract up to 4 `<loc>` URLs from the same domain.
3. If not found or empty: load homepage with Playwright, extract `<a href>` tags, filter to same-domain, take first 4.
4. Always prepend the homepage URL. Deduplicate. Cap at 5 total.

### Step 3 — Scrape each URL (per-page try/except)
For each URL:
```
try:
    Playwright: navigate(url, timeout=30s)
    - record load_time_ms (navigationEnd timing)
    - record status_code from response
    - capture full HTML
    BeautifulSoup(html):
    - meta_title       → <title> text
    - meta_description → <meta name="description"> content
    - h1_tags          → list of <h1> text
    - h2_tags          → list of <h2> text
    - internal_links   → list of same-domain <a href> values
    - image_alts       → list of <img alt> values (empty string if alt missing)
    - extracted_text   → stripped visible text (exclude script/style)
    Derive:
    - https → url.startswith("https://")
    Save ScrapedPage record
except Exception as e:
    log warning with url + error; continue to next page
```

### Step 4 — Finalise
- If ≥1 `ScrapedPage` saved: `AuditJob.status = "complete"`, `completed_at = now()`
- If 0 pages saved: `AuditJob.status = "failed"`, `error_message = last_error`

---

## Data Model Change

Add to `ScrapedPage`:
```python
image_alts = models.JSONField(default=list)
```
New migration: `0003_scrapedpage_image_alts`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Individual page timeout / parse error | Log warning, skip page, continue |
| Domain unreachable (all pages fail) | AuditJob → `failed` with error_message |
| AuditJob ID not found | Task raises `AuditJob.DoesNotExist`, logged as error |
| Sitemap malformed | Catch parse error, fall back to link extraction |

---

## Dependencies to Add

```
playwright==1.44.0
beautifulsoup4==4.12.3
lxml==5.2.2
requests==2.32.3
```

Dockerfile addition (after `pip install`):
```dockerfile
RUN playwright install chromium --with-deps
```

---

## Done Criteria

Triggering `POST /api/businesses/:id/audit/` on a real URL produces:
- `AuditJob.status == "complete"`
- ≥1 `ScrapedPage` record with `meta_title`, `h1_tags`, `load_time_ms`, `status_code` populated
