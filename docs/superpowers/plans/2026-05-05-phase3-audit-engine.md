# Phase 3 — Audit Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn scraped page data into a structured AuditReport with per-category scores and AuditIssue records.

**Architecture:** A `scorers/` package holds five independent scorer modules (SEO + Tech deterministic, Conversion + Content + Trust via Claude tool-use). A new `run_audit` Celery task orchestrates them and is chained automatically from `scrape_website`. Two new API endpoints expose the report and issues.

**Tech Stack:** Django 4.2, Celery 5.3, Anthropic SDK (`anthropic`), Pydantic v2, Django REST Framework 3.14

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/audits/scorers/__init__.py` |
| Create | `backend/audits/scorers/schemas.py` |
| Create | `backend/audits/scorers/claude_client.py` |
| Create | `backend/audits/scorers/seo.py` |
| Create | `backend/audits/scorers/tech.py` |
| Create | `backend/audits/scorers/conversion.py` |
| Create | `backend/audits/scorers/content.py` |
| Create | `backend/audits/scorers/trust.py` |
| Modify | `backend/requirements.txt` |
| Modify | `backend/audits/tasks.py` |
| Modify | `backend/audits/serializers.py` |
| Modify | `backend/audits/views.py` |
| Modify | `backend/audits/urls.py` |
| Modify | `backend/CLAUDE.md` |
| Create | `backend/audits/tests/test_scorers_seo.py` |
| Create | `backend/audits/tests/test_scorers_tech.py` |
| Create | `backend/audits/tests/test_scorers_claude_client.py` |
| Create | `backend/audits/tests/test_scorers_conversion.py` |
| Create | `backend/audits/tests/test_scorers_content.py` |
| Create | `backend/audits/tests/test_scorers_trust.py` |
| Create | `backend/audits/tests/test_run_audit.py` |
| Create | `backend/audits/tests/test_audit_views.py` |

---

## Task 1: Add dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add anthropic and pydantic to requirements**

Replace the contents of `backend/requirements.txt` with:

```
Django==4.2.13
djangorestframework==3.14.0
psycopg2-binary==2.9.9
django-environ==0.11.2
pgvector==0.3.3
celery==5.3.6
redis==5.0.4
django-cors-headers==4.3.1
playwright==1.44.0
beautifulsoup4==4.12.3
lxml==5.2.2
requests==2.32.3
anthropic==0.40.0
pydantic==2.7.1
```

- [ ] **Step 2: Rebuild the Docker image**

```bash
docker compose build backend
```

Expected: Build completes with no errors.

- [ ] **Step 3: Verify imports work**

```bash
docker compose run --rm backend python -c "import anthropic; import pydantic; print('OK')"
```

Expected: prints `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add anthropic and pydantic dependencies"
```

---

## Task 2: Shared Pydantic schemas

**Files:**
- Create: `backend/audits/scorers/__init__.py`
- Create: `backend/audits/scorers/schemas.py`

- [ ] **Step 1: Write the failing test**

Create `backend/audits/tests/test_scorers_schemas.py`:

```python
from django.test import SimpleTestCase
from audits.scorers.schemas import CategoryResult, ParameterResult


class ParameterResultTest(SimpleTestCase):
    def test_valid_parameter(self):
        p = ParameterResult(key='meta_title', score=7, rationale='Title is good.')
        self.assertEqual(p.key, 'meta_title')
        self.assertEqual(p.score, 7)

    def test_model_dump(self):
        p = ParameterResult(key='h1_tag', score=0, rationale='Missing.')
        d = p.model_dump()
        self.assertEqual(d, {'key': 'h1_tag', 'score': 0, 'rationale': 'Missing.'})


class CategoryResultTest(SimpleTestCase):
    def _make(self, **kwargs):
        defaults = dict(
            category='seo', score=70,
            parameters=[ParameterResult(key='meta_title', score=7, rationale='OK')],
            top_issues=[], summary='Looks good.'
        )
        defaults.update(kwargs)
        return CategoryResult(**defaults)

    def test_valid_category_result(self):
        r = self._make()
        self.assertEqual(r.category, 'seo')
        self.assertEqual(r.score, 70)

    def test_model_dump_includes_parameters(self):
        r = self._make()
        d = r.model_dump()
        self.assertIn('parameters', d)
        self.assertEqual(d['parameters'][0]['key'], 'meta_title')
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_schemas -v 2
```

Expected: `ModuleNotFoundError: No module named 'audits.scorers'`

- [ ] **Step 3: Create the scorers package and schemas module**

Create `backend/audits/scorers/__init__.py` (empty file).

Create `backend/audits/scorers/schemas.py`:

```python
from pydantic import BaseModel


class ParameterResult(BaseModel):
    key: str
    score: int
    rationale: str


class CategoryResult(BaseModel):
    category: str
    score: int
    parameters: list[ParameterResult]
    top_issues: list[str]
    summary: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_schemas -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scorers/ backend/audits/tests/test_scorers_schemas.py
git commit -m "feat: add scorers package with shared Pydantic schemas"
```

---

## Task 3: SEO scorer

**Files:**
- Create: `backend/audits/scorers/seo.py`
- Create: `backend/audits/tests/test_scorers_seo.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_scorers_seo.py`:

```python
from unittest.mock import MagicMock
from django.test import SimpleTestCase
from audits.scorers.seo import score_seo
from audits.models import ScrapedPage


def make_page(**kwargs):
    page = MagicMock(spec=ScrapedPage)
    page.meta_title = kwargs.get('meta_title', 'A Good Title That Is Fifty Five Characters')
    page.meta_description = kwargs.get('meta_description', 'A' * 155)
    page.h1_tags = kwargs.get('h1_tags', ['Main Heading'])
    page.h2_tags = kwargs.get('h2_tags', [])
    page.image_alts = kwargs.get('image_alts', ['alt text', 'another alt'])
    page.internal_links = kwargs.get('internal_links', ['/a', '/b', '/c'])
    page.html_content = kwargs.get('html_content', '<link rel="canonical" href="/">')
    return page


class SEOScorerTest(SimpleTestCase):
    def test_perfect_page_scores_100(self):
        result = score_seo(make_page())
        self.assertEqual(result.category, 'seo')
        self.assertGreaterEqual(result.score, 90)

    def test_meta_title_missing_scores_zero_for_that_param(self):
        result = score_seo(make_page(meta_title=''))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 0)

    def test_meta_title_wrong_length_scores_five(self):
        result = score_seo(make_page(meta_title='Short'))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 5)

    def test_meta_title_optimal_length_scores_ten(self):
        result = score_seo(make_page(meta_title='A' * 55))
        param = next(p for p in result.parameters if p.key == 'meta_title')
        self.assertEqual(param.score, 10)

    def test_meta_description_missing_scores_zero(self):
        result = score_seo(make_page(meta_description=''))
        param = next(p for p in result.parameters if p.key == 'meta_description')
        self.assertEqual(param.score, 0)

    def test_h1_exactly_one_scores_ten(self):
        result = score_seo(make_page(h1_tags=['Only Heading']))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 10)

    def test_h1_multiple_scores_five(self):
        result = score_seo(make_page(h1_tags=['H1', 'H1 Again']))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 5)

    def test_h1_missing_scores_zero(self):
        result = score_seo(make_page(h1_tags=[]))
        param = next(p for p in result.parameters if p.key == 'h1_tag')
        self.assertEqual(param.score, 0)

    def test_image_alts_all_present_scores_ten(self):
        result = score_seo(make_page(image_alts=['alt1', 'alt2']))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 10)

    def test_image_alts_some_missing_scales_score(self):
        result = score_seo(make_page(image_alts=['alt', '', '']))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 3)

    def test_no_images_scores_ten(self):
        result = score_seo(make_page(image_alts=[]))
        param = next(p for p in result.parameters if p.key == 'image_alts')
        self.assertEqual(param.score, 10)

    def test_three_internal_links_scores_ten(self):
        result = score_seo(make_page(internal_links=['/a', '/b', '/c']))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 10)

    def test_one_internal_link_scores_five(self):
        result = score_seo(make_page(internal_links=['/a']))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 5)

    def test_no_internal_links_scores_zero(self):
        result = score_seo(make_page(internal_links=[]))
        param = next(p for p in result.parameters if p.key == 'internal_links')
        self.assertEqual(param.score, 0)

    def test_canonical_present_scores_ten(self):
        result = score_seo(make_page(html_content='<link rel="canonical" href="/">'))
        param = next(p for p in result.parameters if p.key == 'canonical_tag')
        self.assertEqual(param.score, 10)

    def test_canonical_absent_scores_zero(self):
        result = score_seo(make_page(html_content='<html></html>'))
        param = next(p for p in result.parameters if p.key == 'canonical_tag')
        self.assertEqual(param.score, 0)

    def test_returns_six_parameters(self):
        result = score_seo(make_page())
        self.assertEqual(len(result.parameters), 6)

    def test_top_issues_contains_low_scoring_params(self):
        result = score_seo(make_page(meta_title='', h1_tags=[]))
        self.assertIn('meta_title', result.top_issues)
        self.assertIn('h1_tag', result.top_issues)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_seo -v 2
```

Expected: `ModuleNotFoundError: No module named 'audits.scorers.seo'`

- [ ] **Step 3: Implement the SEO scorer**

Create `backend/audits/scorers/seo.py`:

```python
from statistics import mean

from audits.models import ScrapedPage

from .schemas import CategoryResult, ParameterResult


def score_seo(page: ScrapedPage) -> CategoryResult:
    params = [
        _score_meta_title(page),
        _score_meta_description(page),
        _score_h1(page),
        _score_image_alts(page),
        _score_internal_links(page),
        _score_canonical(page),
    ]
    score = round(mean(p.score for p in params) * 10)
    top_issues = [p.key for p in params if p.score <= 5]
    return CategoryResult(
        category='seo',
        score=score,
        parameters=params,
        top_issues=top_issues,
        summary=_summary(score),
    )


def _score_meta_title(page: ScrapedPage) -> ParameterResult:
    title = page.meta_title or ''
    if not title:
        return ParameterResult(key='meta_title', score=0, rationale='Meta title is missing.')
    length = len(title)
    if 50 <= length <= 60:
        return ParameterResult(key='meta_title', score=10, rationale=f'Meta title is {length} chars (optimal 50–60).')
    return ParameterResult(key='meta_title', score=5, rationale=f'Meta title is {length} chars; optimal is 50–60.')


def _score_meta_description(page: ScrapedPage) -> ParameterResult:
    desc = page.meta_description or ''
    if not desc:
        return ParameterResult(key='meta_description', score=0, rationale='Meta description is missing.')
    length = len(desc)
    if 150 <= length <= 160:
        return ParameterResult(key='meta_description', score=10, rationale=f'Meta description is {length} chars (optimal 150–160).')
    return ParameterResult(key='meta_description', score=5, rationale=f'Meta description is {length} chars; optimal is 150–160.')


def _score_h1(page: ScrapedPage) -> ParameterResult:
    count = len(page.h1_tags or [])
    if count == 1:
        return ParameterResult(key='h1_tag', score=10, rationale='Page has exactly one H1 tag.')
    if count > 1:
        return ParameterResult(key='h1_tag', score=5, rationale=f'Page has {count} H1 tags; should have exactly one.')
    return ParameterResult(key='h1_tag', score=0, rationale='No H1 tag found on the page.')


def _score_image_alts(page: ScrapedPage) -> ParameterResult:
    alts = page.image_alts or []
    total = len(alts)
    if total == 0:
        return ParameterResult(key='image_alts', score=10, rationale='No images found; no alt text issues.')
    present = sum(1 for alt in alts if alt.strip())
    ratio_score = round(10 * present / total)
    if ratio_score == 10:
        return ParameterResult(key='image_alts', score=10, rationale=f'All {total} images have alt text.')
    missing = total - present
    return ParameterResult(key='image_alts', score=ratio_score, rationale=f'{missing} of {total} images are missing alt text.')


def _score_internal_links(page: ScrapedPage) -> ParameterResult:
    count = len(page.internal_links or [])
    if count >= 3:
        return ParameterResult(key='internal_links', score=10, rationale=f'{count} internal links found (3+ is optimal).')
    if count >= 1:
        return ParameterResult(key='internal_links', score=5, rationale=f'Only {count} internal link(s) found; aim for 3+.')
    return ParameterResult(key='internal_links', score=0, rationale='No internal links found.')


def _score_canonical(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    if 'rel="canonical"' in html or "rel='canonical'" in html:
        return ParameterResult(key='canonical_tag', score=10, rationale='Canonical tag is present.')
    return ParameterResult(key='canonical_tag', score=0, rationale='No canonical tag found.')


def _summary(score: int) -> str:
    if score >= 80:
        return 'SEO fundamentals are in good shape.'
    if score >= 50:
        return 'Several SEO basics need attention.'
    return 'Critical SEO issues require immediate fixes.'
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_seo -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scorers/seo.py backend/audits/tests/test_scorers_seo.py
git commit -m "feat: add deterministic SEO scorer"
```

---

## Task 4: Tech scorer

**Files:**
- Create: `backend/audits/scorers/tech.py`
- Create: `backend/audits/tests/test_scorers_tech.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_scorers_tech.py`:

```python
from unittest.mock import MagicMock
from django.test import SimpleTestCase
from audits.scorers.tech import score_tech
from audits.models import ScrapedPage


def make_page(**kwargs):
    page = MagicMock(spec=ScrapedPage)
    page.https = kwargs.get('https', True)
    page.load_time_ms = kwargs.get('load_time_ms', 800)
    page.html_content = kwargs.get('html_content', (
        '<head><meta name="viewport" content="width=device-width"></head>'
        '<body>cookiebot</body>'
    ))
    return page


def make_pages(statuses):
    pages = []
    for code in statuses:
        p = MagicMock(spec=ScrapedPage)
        p.status_code = code
        pages.append(p)
    return pages


class TechScorerTest(SimpleTestCase):
    def test_returns_six_parameters(self):
        result = score_tech(make_page(), make_pages([200]))
        self.assertEqual(len(result.parameters), 6)

    def test_category_is_tech(self):
        result = score_tech(make_page(), make_pages([200]))
        self.assertEqual(result.category, 'tech')

    def test_https_true_scores_ten(self):
        result = score_tech(make_page(https=True), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'https')
        self.assertEqual(param.score, 10)

    def test_https_false_scores_zero(self):
        result = score_tech(make_page(https=False), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'https')
        self.assertEqual(param.score, 0)

    def test_load_time_fast_scores_ten(self):
        result = score_tech(make_page(load_time_ms=500), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 10)

    def test_load_time_medium_scores_five(self):
        result = score_tech(make_page(load_time_ms=3000), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 5)

    def test_load_time_slow_scores_zero(self):
        result = score_tech(make_page(load_time_ms=5000), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 0)

    def test_load_time_none_scores_five(self):
        result = score_tech(make_page(load_time_ms=None), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'load_time')
        self.assertEqual(param.score, 5)

    def test_viewport_present_scores_ten(self):
        html = '<head><meta name="viewport" content="width=device-width"></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'mobile_viewport')
        self.assertEqual(param.score, 10)

    def test_viewport_absent_scores_zero(self):
        result = score_tech(make_page(html_content='<head></head>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'mobile_viewport')
        self.assertEqual(param.score, 0)

    def test_no_blocking_scripts_scores_ten(self):
        html = '<head><script defer src="a.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 10)

    def test_two_blocking_scripts_scores_five(self):
        html = '<head><script src="a.js"></script><script src="b.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 5)

    def test_three_blocking_scripts_scores_zero(self):
        html = '<head><script src="a.js"></script><script src="b.js"></script><script src="c.js"></script></head>'
        result = score_tech(make_page(html_content=html), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'render_blocking_js')
        self.assertEqual(param.score, 0)

    def test_no_broken_links_scores_ten(self):
        result = score_tech(make_page(), make_pages([200, 200, 200]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 10)

    def test_one_broken_link_scores_five(self):
        result = score_tech(make_page(), make_pages([200, 404]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 5)

    def test_two_broken_links_scores_zero(self):
        result = score_tech(make_page(), make_pages([404, 500]))
        param = next(p for p in result.parameters if p.key == 'broken_links')
        self.assertEqual(param.score, 0)

    def test_cookie_consent_present_scores_ten(self):
        result = score_tech(make_page(html_content='<div class="cookiebot">accept</div>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'cookie_consent')
        self.assertEqual(param.score, 10)

    def test_cookie_consent_absent_scores_five(self):
        result = score_tech(make_page(html_content='<html></html>'), make_pages([200]))
        param = next(p for p in result.parameters if p.key == 'cookie_consent')
        self.assertEqual(param.score, 5)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_tech -v 2
```

Expected: `ModuleNotFoundError: No module named 'audits.scorers.tech'`

- [ ] **Step 3: Implement the Tech scorer**

Create `backend/audits/scorers/tech.py`:

```python
import re
from statistics import mean

from audits.models import ScrapedPage

from .schemas import CategoryResult, ParameterResult


def score_tech(page: ScrapedPage, all_pages: list) -> CategoryResult:
    params = [
        _score_https(page),
        _score_load_time(page),
        _score_mobile_viewport(page),
        _score_render_blocking_js(page),
        _score_broken_links(all_pages),
        _score_cookie_consent(page),
    ]
    score = round(mean(p.score for p in params) * 10)
    top_issues = [p.key for p in params if p.score <= 5]
    return CategoryResult(
        category='tech',
        score=score,
        parameters=params,
        top_issues=top_issues,
        summary=_summary(score),
    )


def _score_https(page: ScrapedPage) -> ParameterResult:
    if page.https:
        return ParameterResult(key='https', score=10, rationale='Site is served over HTTPS.')
    return ParameterResult(key='https', score=0, rationale='Site is not served over HTTPS — a critical security issue.')


def _score_load_time(page: ScrapedPage) -> ParameterResult:
    ms = page.load_time_ms
    if ms is None:
        return ParameterResult(key='load_time', score=5, rationale='Load time could not be measured.')
    if ms < 2000:
        return ParameterResult(key='load_time', score=10, rationale=f'Page loaded in {ms}ms (under 2s is optimal).')
    if ms < 4000:
        return ParameterResult(key='load_time', score=5, rationale=f'Page loaded in {ms}ms; aim for under 2s.')
    return ParameterResult(key='load_time', score=0, rationale=f'Page loaded in {ms}ms — very slow, over 4s.')


def _score_mobile_viewport(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    if 'name="viewport"' in html or "name='viewport'" in html:
        return ParameterResult(key='mobile_viewport', score=10, rationale='Mobile viewport meta tag is present.')
    return ParameterResult(key='mobile_viewport', score=0, rationale='No mobile viewport meta tag found.')


def _score_render_blocking_js(page: ScrapedPage) -> ParameterResult:
    html = page.html_content or ''
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL | re.IGNORECASE)
    if not head_match:
        return ParameterResult(key='render_blocking_js', score=10, rationale='No <head> section found to inspect.')
    head_html = head_match.group(1)
    scripts = re.findall(r'<script[^>]*>', head_html, re.IGNORECASE)
    blocking = [s for s in scripts if 'defer' not in s and 'async' not in s and 'type="module"' not in s]
    count = len(blocking)
    if count == 0:
        return ParameterResult(key='render_blocking_js', score=10, rationale='No render-blocking scripts in <head>.')
    if count <= 2:
        return ParameterResult(key='render_blocking_js', score=5, rationale=f'{count} render-blocking script(s) in <head>.')
    return ParameterResult(key='render_blocking_js', score=0, rationale=f'{count} render-blocking scripts in <head>.')


def _score_broken_links(all_pages: list) -> ParameterResult:
    broken = [p for p in all_pages if p.status_code is not None and p.status_code >= 400]
    count = len(broken)
    if count == 0:
        return ParameterResult(key='broken_links', score=10, rationale='No broken links detected across scraped pages.')
    if count == 1:
        return ParameterResult(key='broken_links', score=5, rationale=f'1 broken link detected (HTTP {broken[0].status_code}).')
    return ParameterResult(key='broken_links', score=0, rationale=f'{count} broken links detected across scraped pages.')


def _score_cookie_consent(page: ScrapedPage) -> ParameterResult:
    html = (page.html_content or '').lower()
    patterns = ['cookiebot', 'cookie-consent', 'gdpr', 'cookie-law', 'cookie_notice', 'cookiebanner']
    if any(pat in html for pat in patterns):
        return ParameterResult(key='cookie_consent', score=10, rationale='Cookie consent banner detected.')
    return ParameterResult(key='cookie_consent', score=5, rationale='No cookie consent banner detected.')


def _summary(score: int) -> str:
    if score >= 80:
        return 'Technical foundations are solid.'
    if score >= 50:
        return 'Some technical improvements would benefit performance and compliance.'
    return 'Significant technical issues are impacting the site.'
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_tech -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scorers/tech.py backend/audits/tests/test_scorers_tech.py
git commit -m "feat: add deterministic Tech scorer"
```

---

## Task 5: Claude client with retry and logging

**Files:**
- Create: `backend/audits/scorers/claude_client.py`
- Create: `backend/audits/tests/test_scorers_claude_client.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_scorers_claude_client.py`:

```python
import json
from unittest.mock import MagicMock, patch, call
from django.test import SimpleTestCase
from audits.scorers.claude_client import score_with_claude
from audits.scorers.schemas import CategoryResult


def _make_mock_response(tool_input: dict):
    block = MagicMock()
    block.type = 'tool_use'
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 50
    return response


VALID_TOOL_INPUT = {
    'category': 'conversion',
    'score': 72,
    'parameters': [{'key': 'cta_clarity', 'score': 8, 'rationale': 'CTA is clear.'}],
    'top_issues': [],
    'summary': 'Good conversion signals.',
}


class ClaudeClientTest(SimpleTestCase):
    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_success_returns_category_result(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertIsInstance(result, CategoryResult)
        self.assertEqual(result.category, 'conversion')
        self.assertEqual(result.score, 72)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_success_calls_api_once(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(MockClient.return_value.messages.create.call_count, 1)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_retries_three_times_on_failure(self, MockClient):
        MockClient.return_value.messages.create.side_effect = Exception('API error')
        score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(MockClient.return_value.messages.create.call_count, 3)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_fallback_score_on_all_failures(self, MockClient):
        MockClient.return_value.messages.create.side_effect = Exception('API error')
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(result.score, 50)
        self.assertEqual(result.parameters, [])
        self.assertEqual(result.category, 'conversion')

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_succeeds_on_second_attempt(self, MockClient):
        MockClient.return_value.messages.create.side_effect = [
            Exception('first fail'),
            _make_mock_response(VALID_TOOL_INPUT),
        ]
        result = score_with_claude('conversion', 'test prompt', 'conversion-v1')
        self.assertEqual(result.score, 72)
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)

    @patch('audits.scorers.claude_client.anthropic.Anthropic')
    def test_logs_json_on_success(self, MockClient):
        MockClient.return_value.messages.create.return_value = _make_mock_response(VALID_TOOL_INPUT)
        with self.assertLogs('audits.scorers.claude_client', level='INFO') as cm:
            score_with_claude('conversion', 'test prompt', 'conversion-v1')
        log_record = json.loads(cm.output[0].split('INFO:audits.scorers.claude_client:')[1])
        self.assertEqual(log_record['event'], 'llm_call')
        self.assertTrue(log_record['success'])
        self.assertEqual(log_record['prompt_version'], 'conversion-v1')
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_claude_client -v 2
```

Expected: `ModuleNotFoundError: No module named 'audits.scorers.claude_client'`

- [ ] **Step 3: Implement the Claude client**

Create `backend/audits/scorers/claude_client.py`:

```python
import json
import logging
import time

import anthropic

from .schemas import CategoryResult, ParameterResult

logger = logging.getLogger(__name__)

_COST_PER_INPUT_TOKEN = 3.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000

_TOOL_DEFINITION = {
    'name': 'submit_category_result',
    'description': 'Submit the structured audit result for a category.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'category': {'type': 'string'},
            'score': {'type': 'integer', 'minimum': 0, 'maximum': 100},
            'parameters': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'key': {'type': 'string'},
                        'score': {'type': 'integer', 'minimum': 0, 'maximum': 10},
                        'rationale': {'type': 'string'},
                    },
                    'required': ['key', 'score', 'rationale'],
                },
            },
            'top_issues': {'type': 'array', 'items': {'type': 'string'}},
            'summary': {'type': 'string'},
        },
        'required': ['category', 'score', 'parameters', 'top_issues', 'summary'],
    },
}


def score_with_claude(category: str, prompt: str, prompt_version: str) -> CategoryResult:
    client = anthropic.Anthropic()

    for attempt in range(1, 4):
        t_start = time.monotonic()
        input_tokens = 0
        output_tokens = 0
        try:
            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=1024,
                tools=[_TOOL_DEFINITION],
                tool_choice={'type': 'tool', 'name': 'submit_category_result'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            latency_ms = int((time.monotonic() - t_start) * 1000)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            tool_block = next((b for b in response.content if b.type == 'tool_use'), None)
            if tool_block is None:
                raise ValueError('No tool_use block in response')

            result = CategoryResult(**tool_block.input)
            _log(category, input_tokens, output_tokens, latency_ms, prompt_version, attempt, True)
            return result

        except Exception as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            _log(category, input_tokens, output_tokens, latency_ms, prompt_version, attempt, False, str(exc))
            logger.warning(f'LLM scoring attempt {attempt}/3 failed for {category}: {exc}')

    logger.error(f'All 3 LLM scoring attempts failed for {category}, using fallback')
    return CategoryResult(
        category=category,
        score=50,
        parameters=[],
        top_issues=[],
        summary='Score unavailable — LLM evaluation failed after 3 attempts.',
    )


def _log(category, input_tokens, output_tokens, latency_ms, prompt_version, attempt, success, error=None):
    cost_usd = (input_tokens * _COST_PER_INPUT_TOKEN) + (output_tokens * _COST_PER_OUTPUT_TOKEN)
    record = {
        'event': 'llm_call',
        'category': category,
        'model': 'claude-sonnet-4-6',
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'latency_ms': latency_ms,
        'cost_usd': round(cost_usd, 6),
        'prompt_version': prompt_version,
        'attempt': attempt,
        'success': success,
    }
    if error:
        record['error'] = error
    logger.info(json.dumps(record))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_claude_client -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scorers/claude_client.py backend/audits/tests/test_scorers_claude_client.py
git commit -m "feat: add Claude client with retry logic and structured JSON logging"
```

---

## Task 6: Conversion, Content, and Trust LLM scorers

**Files:**
- Create: `backend/audits/scorers/conversion.py`
- Create: `backend/audits/scorers/content.py`
- Create: `backend/audits/scorers/trust.py`
- Create: `backend/audits/tests/test_scorers_llm.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_scorers_llm.py`:

```python
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from audits.models import ScrapedPage
from audits.scorers.schemas import CategoryResult, ParameterResult


def make_page():
    page = MagicMock(spec=ScrapedPage)
    page.meta_title = 'Example Site'
    page.meta_description = 'We help you grow.'
    page.h1_tags = ['Grow Your Business']
    page.h2_tags = ['Features', 'Pricing']
    page.extracted_text = 'We help businesses grow with AI tools.'
    return page


def make_category_result(category):
    return CategoryResult(
        category=category,
        score=65,
        parameters=[ParameterResult(key='cta_clarity', score=6, rationale='CTA is weak.')],
        top_issues=['cta_clarity'],
        summary='Needs improvement.',
    )


class ConversionScorerTest(SimpleTestCase):
    @patch('audits.scorers.conversion.score_with_claude')
    def test_calls_score_with_claude(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        result = score_conversion(make_page())
        mock_claude.assert_called_once()
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'conversion')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'conversion-v1')

    @patch('audits.scorers.conversion.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        result = score_conversion(make_page())
        self.assertIsInstance(result, CategoryResult)
        self.assertEqual(result.score, 65)

    @patch('audits.scorers.conversion.score_with_claude')
    def test_prompt_includes_page_text(self, mock_claude):
        from audits.scorers.conversion import score_conversion
        mock_claude.return_value = make_category_result('conversion')
        page = make_page()
        page.extracted_text = 'unique-sentinel-text-xyz'
        score_conversion(page)
        prompt_arg = mock_claude.call_args[1]['prompt']
        self.assertIn('unique-sentinel-text-xyz', prompt_arg)


class ContentScorerTest(SimpleTestCase):
    @patch('audits.scorers.content.score_with_claude')
    def test_calls_score_with_claude_content_version(self, mock_claude):
        from audits.scorers.content import score_content
        mock_claude.return_value = make_category_result('content')
        score_content(make_page())
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'content')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'content-v1')

    @patch('audits.scorers.content.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.content import score_content
        mock_claude.return_value = make_category_result('content')
        result = score_content(make_page())
        self.assertIsInstance(result, CategoryResult)


class TrustScorerTest(SimpleTestCase):
    @patch('audits.scorers.trust.score_with_claude')
    def test_calls_score_with_claude_trust_version(self, mock_claude):
        from audits.scorers.trust import score_trust
        mock_claude.return_value = make_category_result('trust')
        score_trust(make_page())
        call_kwargs = mock_claude.call_args
        self.assertEqual(call_kwargs[1]['category'], 'trust')
        self.assertEqual(call_kwargs[1]['prompt_version'], 'trust-v1')

    @patch('audits.scorers.trust.score_with_claude')
    def test_returns_category_result(self, mock_claude):
        from audits.scorers.trust import score_trust
        mock_claude.return_value = make_category_result('trust')
        result = score_trust(make_page())
        self.assertIsInstance(result, CategoryResult)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_llm -v 2
```

Expected: `ModuleNotFoundError: No module named 'audits.scorers.conversion'`

- [ ] **Step 3: Implement the three LLM scorers**

Create `backend/audits/scorers/conversion.py`:

```python
from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'conversion-v1'

_RUBRIC = """
Evaluate this website page on CONVERSION potential. Score each parameter 0-10:

- cta_clarity (0-10): Is the primary CTA clear, specific, and compelling? Above the fold? Benefit language?
- value_proposition (0-10): Is the value proposition clear in one sentence (who, what, why)?
- social_proof (0-10): Are testimonials, logos, reviews, or case studies present?
- pricing_transparency (0-10): Is pricing visible or is there a clear path to pricing?
- form_field_count (0-10): Are forms minimal? Score 10 for ≤3 fields, 5 for 4-6 fields, 0 for 7+ fields. Score 8 if no forms present.

Return a submit_category_result tool call with category="conversion".
"""


def score_conversion(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='conversion',
        prompt=_build_prompt(page),
        prompt_version=PROMPT_VERSION,
    )


def _build_prompt(page: ScrapedPage) -> str:
    text = (page.extracted_text or '')[:3000]
    h2s = ', '.join(page.h2_tags[:5]) if page.h2_tags else '(none)'
    return (
        f"{_RUBRIC}\n\nPage data:\n"
        f"- Meta title: {page.meta_title or '(none)'}\n"
        f"- Meta description: {page.meta_description or '(none)'}\n"
        f"- H1 tags: {', '.join(page.h1_tags) if page.h1_tags else '(none)'}\n"
        f"- H2 tags: {h2s}\n"
        f"- Page text (first 3000 chars):\n{text}"
    )
```

Create `backend/audits/scorers/content.py`:

```python
from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'content-v1'

_RUBRIC = """
Evaluate this website page on CONTENT quality. Score each parameter 0-10:

- headline_pain_point (0-10): Does the main headline address a real customer pain point?
- benefits_vs_features (0-10): Does the copy focus on benefits to the customer rather than just product features?
- reading_level (0-10): Is the reading level appropriate and accessible for the target audience?
- brand_voice (0-10): Is the brand voice consistent and distinct across headings and body copy?
- content_depth (0-10): Is there sufficient content depth — informative without being overwhelming?

Return a submit_category_result tool call with category="content".
"""


def score_content(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='content',
        prompt=_build_prompt(page),
        prompt_version=PROMPT_VERSION,
    )


def _build_prompt(page: ScrapedPage) -> str:
    text = (page.extracted_text or '')[:3000]
    h2s = ', '.join(page.h2_tags[:5]) if page.h2_tags else '(none)'
    return (
        f"{_RUBRIC}\n\nPage data:\n"
        f"- Meta title: {page.meta_title or '(none)'}\n"
        f"- Meta description: {page.meta_description or '(none)'}\n"
        f"- H1 tags: {', '.join(page.h1_tags) if page.h1_tags else '(none)'}\n"
        f"- H2 tags: {h2s}\n"
        f"- Page text (first 3000 chars):\n{text}"
    )
```

Create `backend/audits/scorers/trust.py`:

```python
from audits.models import ScrapedPage

from .claude_client import score_with_claude
from .schemas import CategoryResult

PROMPT_VERSION = 'trust-v1'

_RUBRIC = """
Evaluate this website page on TRUST signals. Score each parameter 0-10:

- testimonials (0-10): Are testimonials, case studies, or customer reviews present?
- about_page (0-10): Is there an About page or team information visible or linked?
- contact_info (0-10): Is contact information (email, phone, address) clearly visible?
- privacy_policy (0-10): Are privacy policy and/or terms of service links present?
- trust_badges (0-10): Are there certifications, security badges, accreditations, or partner logos?

Return a submit_category_result tool call with category="trust".
"""


def score_trust(page: ScrapedPage) -> CategoryResult:
    return score_with_claude(
        category='trust',
        prompt=_build_prompt(page),
        prompt_version=PROMPT_VERSION,
    )


def _build_prompt(page: ScrapedPage) -> str:
    text = (page.extracted_text or '')[:3000]
    h2s = ', '.join(page.h2_tags[:5]) if page.h2_tags else '(none)'
    return (
        f"{_RUBRIC}\n\nPage data:\n"
        f"- Meta title: {page.meta_title or '(none)'}\n"
        f"- Meta description: {page.meta_description or '(none)'}\n"
        f"- H1 tags: {', '.join(page.h1_tags) if page.h1_tags else '(none)'}\n"
        f"- H2 tags: {h2s}\n"
        f"- Page text (first 3000 chars):\n{text}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_scorers_llm -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scorers/conversion.py backend/audits/scorers/content.py backend/audits/scorers/trust.py backend/audits/tests/test_scorers_llm.py
git commit -m "feat: add Conversion, Content, and Trust LLM scorers"
```

---

## Task 7: run_audit Celery task

**Files:**
- Modify: `backend/audits/tasks.py`
- Create: `backend/audits/tests/test_run_audit.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_run_audit.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from audits.models import AuditJob, AuditReport, AuditIssue, Business, ScrapedPage
from audits.scorers.schemas import CategoryResult, ParameterResult


def make_category_result(category, score, params):
    return CategoryResult(
        category=category,
        score=score,
        parameters=[ParameterResult(key=k, score=s, rationale='test') for k, s in params],
        top_issues=[k for k, s in params if s <= 5],
        summary='Test summary.',
    )


MOCK_RESULTS = {
    'seo': make_category_result('seo', 80, [('meta_title', 10), ('h1_tag', 0)]),
    'tech': make_category_result('tech', 60, [('https', 10), ('load_time', 2)]),
    'conversion': make_category_result('conversion', 70, [('cta_clarity', 8)]),
    'content': make_category_result('content', 75, [('headline_pain_point', 7)]),
    'trust': make_category_result('trust', 50, [('testimonials', 3)]),
}


class RunAuditTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='running')
        ScrapedPage.objects.create(
            business=self.business,
            audit_job=self.job,
            url='https://example.com',
            html_content='<html></html>',
            extracted_text='Test content',
            meta_title='Test',
            meta_description='Desc',
            h1_tags=['Heading'],
            h2_tags=[],
            image_alts=[],
            internal_links=[],
            https=True,
            status_code=200,
            load_time_ms=800,
        )

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_creates_audit_report(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertIsNotNone(self.job.completed_at)
        report = AuditReport.objects.get(audit_job=self.job)
        self.assertEqual(report.seo_score, 80)
        self.assertEqual(report.tech_score, 60)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_overall_score_is_weighted_average(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        expected = round(80*0.20 + 60*0.20 + 70*0.25 + 75*0.20 + 50*0.15)
        self.assertEqual(report.overall_score, expected)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_creates_issues_for_low_scoring_params(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        mock_seo.return_value = MOCK_RESULTS['seo']
        mock_tech.return_value = MOCK_RESULTS['tech']
        mock_conv.return_value = MOCK_RESULTS['conversion']
        mock_content.return_value = MOCK_RESULTS['content']
        mock_trust.return_value = MOCK_RESULTS['trust']

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        issues = AuditIssue.objects.filter(report=report)
        # h1_tag=0 (critical), load_time=2 (critical), testimonials=3 (critical)
        self.assertGreaterEqual(issues.count(), 3)
        critical = issues.filter(severity='critical')
        self.assertGreaterEqual(critical.count(), 3)

    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_no_issues_for_high_scoring_params(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        all_good = make_category_result('seo', 100, [('meta_title', 10), ('h1_tag', 10)])
        mock_seo.return_value = all_good
        mock_tech.return_value = make_category_result('tech', 100, [('https', 10)])
        mock_conv.return_value = make_category_result('conversion', 100, [('cta_clarity', 10)])
        mock_content.return_value = make_category_result('content', 100, [('headline_pain_point', 10)])
        mock_trust.return_value = make_category_result('trust', 100, [('testimonials', 10)])

        from audits.tasks import run_audit
        run_audit(self.job.id)

        report = AuditReport.objects.get(audit_job=self.job)
        self.assertEqual(AuditIssue.objects.filter(report=report).count(), 0)

    def test_sets_failed_status_when_no_pages(self):
        ScrapedPage.objects.filter(audit_job=self.job).delete()
        from audits.tasks import run_audit
        run_audit(self.job.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')

    @patch('audits.tasks.score_seo', side_effect=RuntimeError('scorer blew up'))
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_sets_failed_status_on_exception(self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo):
        from audits.tasks import run_audit
        run_audit(self.job.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertIn('scorer blew up', self.job.error_message)


class ScrapeWebsiteChainTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='pending')

    @patch('audits.tasks.run_audit')
    @patch('audits.tasks._playwright_scrape')
    def test_chains_run_audit_on_success(self, mock_scrape, mock_run_audit):
        mock_scrape.return_value = [{
            'url': 'https://example.com',
            'html_content': '<html></html>',
            'extracted_text': 'text',
            'meta_title': 'Title',
            'meta_description': 'Desc',
            'h1_tags': [],
            'h2_tags': [],
            'image_alts': [],
            'internal_links': [],
            'https': True,
            'status_code': 200,
            'load_time_ms': 500,
        }]
        from audits.tasks import scrape_website
        scrape_website(self.job.id)
        mock_run_audit.delay.assert_called_once_with(self.job.id)

    @patch('audits.tasks.run_audit')
    @patch('audits.tasks._playwright_scrape')
    def test_does_not_set_complete_status_after_scrape(self, mock_scrape, mock_run_audit):
        mock_scrape.return_value = [{
            'url': 'https://example.com',
            'html_content': '<html></html>',
            'extracted_text': 'text',
            'meta_title': 'Title',
            'meta_description': 'Desc',
            'h1_tags': [],
            'h2_tags': [],
            'image_alts': [],
            'internal_links': [],
            'https': True,
            'status_code': 200,
            'load_time_ms': 500,
        }]
        from audits.tasks import scrape_website
        scrape_website(self.job.id)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.status, 'complete')
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_run_audit -v 2
```

Expected: Tests fail because `run_audit` task doesn't exist yet.

- [ ] **Step 3: Update tasks.py**

Replace the entire contents of `backend/audits/tasks.py` with:

```python
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from celery import shared_task
from django.utils import timezone
from playwright.sync_api import sync_playwright

from .scraper import discover_urls_from_sitemap, extract_page_data, extract_same_domain_links
from .scorers.seo import score_seo
from .scorers.tech import score_tech
from .scorers.conversion import score_conversion
from .scorers.content import score_content
from .scorers.trust import score_trust

logger = logging.getLogger(__name__)


def _playwright_scrape(homepage: str) -> list[dict]:
    """
    Run Playwright in a thread to avoid event-loop conflicts.
    Returns a list of page-data dicts (no ORM calls inside this function —
    Django's SynchronousOnlyOperation fires when sync ORM is used while
    Playwright's internal asyncio loop is running).
    """
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        playwright_page = browser.new_page()

        sitemap_urls = discover_urls_from_sitemap(homepage)
        if sitemap_urls:
            urls = list(dict.fromkeys([homepage] + sitemap_urls))[:5]
        else:
            try:
                playwright_page.goto(homepage, timeout=30000, wait_until='networkidle')
                homepage_html = playwright_page.content()
                fallback_links = extract_same_domain_links(homepage_html, homepage, limit=4)
            except Exception as e:
                logger.warning(f"Failed to load homepage for link discovery {homepage}: {e}")
                fallback_links = []
            urls = list(dict.fromkeys([homepage] + fallback_links))[:5]

        for url in urls:
            try:
                t_start = time.monotonic()
                response = playwright_page.goto(url, timeout=30000, wait_until='networkidle')
                load_time_ms = int((time.monotonic() - t_start) * 1000)
                html = playwright_page.content()
                data = extract_page_data(html, url)
                results.append({
                    'url': url,
                    'html_content': html,
                    'status_code': response.status if response else None,
                    'load_time_ms': load_time_ms,
                    'https': url.startswith('https://'),
                    **data,
                })
                logger.info(f"Scraped {url}")
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")

    return results


@shared_task
def scrape_website(audit_job_id: int):
    from .models import AuditJob, ScrapedPage

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
    except AuditJob.DoesNotExist:
        logger.error(f"AuditJob {audit_job_id} not found — skipping")
        return

    job.status = 'running'
    job.save(update_fields=['status'])

    business = job.business
    root_parsed = urlparse(business.url)
    homepage = f"{root_parsed.scheme}://{root_parsed.netloc}"

    last_error = None
    scraped_pages: list[dict] = []

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_playwright_scrape, homepage)
            scraped_pages = future.result(timeout=180)
    except Exception as e:
        last_error = str(e)
        logger.error(f"Fatal scrape error for job {audit_job_id}: {e}")

    saved_count = 0
    for page_data in scraped_pages:
        try:
            ScrapedPage.objects.create(
                business=business,
                audit_job=job,
                **page_data,
            )
            saved_count += 1
        except Exception as e:
            last_error = str(e)
            logger.warning(f"DB save failed for {page_data.get('url')} (job={audit_job_id}): {e}")

    if saved_count > 0:
        run_audit.delay(audit_job_id)
    else:
        job.status = 'failed'
        job.error_message = last_error or 'No pages could be scraped'
        job.save(update_fields=['status', 'error_message'])


@shared_task
def run_audit(audit_job_id: int):
    from .models import AuditJob, AuditReport, AuditIssue, ScrapedPage

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
    except AuditJob.DoesNotExist:
        logger.error(f"AuditJob {audit_job_id} not found — skipping")
        return

    try:
        all_pages = list(ScrapedPage.objects.filter(audit_job=job))
        if not all_pages:
            job.status = 'failed'
            job.error_message = 'No scraped pages found for audit'
            job.save(update_fields=['status', 'error_message'])
            return

        root_parsed = urlparse(job.business.url)
        homepage_url = f"{root_parsed.scheme}://{root_parsed.netloc}"
        page = next(
            (p for p in all_pages if p.url.rstrip('/') == homepage_url.rstrip('/')),
            all_pages[0],
        )

        seo_result = score_seo(page)
        tech_result = score_tech(page, all_pages)
        conv_result = score_conversion(page)
        content_result = score_content(page)
        trust_result = score_trust(page)

        overall = round(
            seo_result.score * 0.20
            + tech_result.score * 0.20
            + conv_result.score * 0.25
            + content_result.score * 0.20
            + trust_result.score * 0.15
        )

        report = AuditReport.objects.create(
            audit_job=job,
            overall_score=overall,
            seo_score=seo_result.score,
            conversion_score=conv_result.score,
            content_score=content_result.score,
            tech_score=tech_result.score,
            trust_score=trust_result.score,
            raw_llm_response={
                'conversion': conv_result.model_dump(),
                'content': content_result.model_dump(),
                'trust': trust_result.model_dump(),
            },
        )

        for result in [seo_result, tech_result, conv_result, content_result, trust_result]:
            for param in result.parameters:
                if param.score <= 6:
                    AuditIssue.objects.create(
                        report=report,
                        category=result.category,
                        severity='critical' if param.score <= 3 else 'warning',
                        title=param.key.replace('_', ' ').title(),
                        description=param.rationale,
                        parameter_key=param.key,
                        score=param.score,
                    )

        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        logger.info(f"run_audit completed for job {audit_job_id}: overall_score={overall}")

    except Exception as exc:
        logger.error(f"run_audit failed for job {audit_job_id}: {exc}")
        try:
            job.status = 'failed'
            job.error_message = str(exc)
            job.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_run_audit -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/audits/tasks.py backend/audits/tests/test_run_audit.py
git commit -m "feat: add run_audit Celery task and chain from scrape_website"
```

---

## Task 8: Audit report and issues API endpoints

**Files:**
- Modify: `backend/audits/serializers.py`
- Modify: `backend/audits/views.py`
- Modify: `backend/audits/urls.py`
- Create: `backend/audits/tests/test_audit_views.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_audit_views.py`:

```python
from django.test import TestCase
from django.urls import reverse
from audits.models import AuditJob, AuditReport, AuditIssue, Business


class AuditReportDetailViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=72,
            seo_score=80,
            conversion_score=70,
            content_score=75,
            tech_score=60,
            trust_score=65,
        )
        AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Meta Title',
            description='Title is too short.',
            parameter_key='meta_title',
            score=5,
        )
        AuditIssue.objects.create(
            report=self.report,
            category='tech',
            severity='critical',
            title='Https',
            description='Not using HTTPS.',
            parameter_key='https',
            score=0,
        )

    def test_returns_200(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_returns_overall_score(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.json()['overall_score'], 72)

    def test_returns_category_scores(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        data = self.client.get(url).json()
        self.assertEqual(data['seo_score'], 80)
        self.assertEqual(data['tech_score'], 60)

    def test_returns_nested_issues(self):
        url = reverse('audit-report', kwargs={'pk': self.job.pk})
        data = self.client.get(url).json()
        self.assertEqual(len(data['issues']), 2)

    def test_404_for_nonexistent_job(self):
        url = reverse('audit-report', kwargs={'pk': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class AuditIssueListViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job, overall_score=60,
            seo_score=60, conversion_score=60, content_score=60, tech_score=60, trust_score=60,
        )
        AuditIssue.objects.create(
            report=self.report, category='seo', severity='warning',
            title='Meta Title', description='Short title.', parameter_key='meta_title', score=5,
        )
        AuditIssue.objects.create(
            report=self.report, category='tech', severity='critical',
            title='Https', description='No HTTPS.', parameter_key='https', score=0,
        )
        AuditIssue.objects.create(
            report=self.report, category='seo', severity='critical',
            title='H1 Tag', description='No H1.', parameter_key='h1_tag', score=0,
        )

    def test_returns_all_issues(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

    def test_filter_by_category(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?category=seo'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(i['category'] == 'seo' for i in data))

    def test_filter_by_severity(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?severity=critical'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(i['severity'] == 'critical' for i in data))

    def test_filter_by_category_and_severity(self):
        url = reverse('audit-issues', kwargs={'pk': self.job.pk}) + '?category=seo&severity=critical'
        data = self.client.get(url).json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['parameter_key'], 'h1_tag')

    def test_404_for_nonexistent_job(self):
        url = reverse('audit-issues', kwargs={'pk': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_audit_views -v 2
```

Expected: `NoReverseMatch` for `audit-report`

- [ ] **Step 3: Add serializers**

Replace the entire contents of `backend/audits/serializers.py` with:

```python
from rest_framework import serializers

from .models import AuditIssue, AuditJob, AuditReport, Business


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'url', 'industry_type', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AuditJobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditJob
        fields = ['id', 'status', 'triggered_at', 'completed_at', 'error_message']
        read_only_fields = ['id', 'status', 'triggered_at', 'completed_at', 'error_message']


class AuditIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditIssue
        fields = ['id', 'category', 'severity', 'title', 'description', 'parameter_key', 'score', 'created_at']
        read_only_fields = fields


class AuditReportSerializer(serializers.ModelSerializer):
    issues = AuditIssueSerializer(many=True, read_only=True)

    class Meta:
        model = AuditReport
        fields = [
            'id', 'audit_job_id', 'overall_score',
            'seo_score', 'conversion_score', 'content_score', 'tech_score', 'trust_score',
            'created_at', 'issues',
        ]
        read_only_fields = fields
```

- [ ] **Step 4: Add views**

Replace the entire contents of `backend/audits/views.py` with:

```python
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditJob, AuditReport, Business
from .serializers import (
    AuditIssueSerializer,
    AuditJobStatusSerializer,
    AuditReportSerializer,
    BusinessSerializer,
)
from .tasks import scrape_website


class BusinessListCreateView(generics.ListCreateAPIView):
    queryset = Business.objects.all().order_by('-created_at')
    serializer_class = BusinessSerializer


class BusinessDetailView(generics.RetrieveAPIView):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer


class AuditTriggerView(APIView):
    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        job = AuditJob.objects.create(business=business)
        scrape_website.delay(job.id)
        return Response({'audit_job_id': job.id, 'status': job.status}, status=status.HTTP_201_CREATED)


class AuditStatusView(generics.RetrieveAPIView):
    queryset = AuditJob.objects.all()
    serializer_class = AuditJobStatusSerializer


class AuditReportDetailView(generics.RetrieveAPIView):
    serializer_class = AuditReportSerializer

    def get_object(self):
        return get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])


class AuditIssueListView(generics.ListAPIView):
    serializer_class = AuditIssueSerializer

    def get_queryset(self):
        report = get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])
        qs = report.issues.all()
        category = self.request.query_params.get('category')
        severity = self.request.query_params.get('severity')
        if category:
            qs = qs.filter(category=category)
        if severity:
            qs = qs.filter(severity=severity)
        return qs
```

- [ ] **Step 5: Add URL routes**

Replace the entire contents of `backend/audits/urls.py` with:

```python
from django.urls import path

from . import views

urlpatterns = [
    path('businesses/', views.BusinessListCreateView.as_view(), name='business-list'),
    path('businesses/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('businesses/<int:pk>/audit/', views.AuditTriggerView.as_view(), name='audit-trigger'),
    path('audits/<int:pk>/status/', views.AuditStatusView.as_view(), name='audit-status'),
    path('audits/<int:pk>/', views.AuditReportDetailView.as_view(), name='audit-report'),
    path('audits/<int:pk>/issues/', views.AuditIssueListView.as_view(), name='audit-issues'),
]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
docker compose run --rm backend python manage.py test audits.tests.test_audit_views -v 2
```

Expected: `OK`

- [ ] **Step 7: Run the full test suite**

```bash
docker compose run --rm backend python manage.py test audits -v 2
```

Expected: All tests pass with `OK`.

- [ ] **Step 8: Commit**

```bash
git add backend/audits/serializers.py backend/audits/views.py backend/audits/urls.py backend/audits/tests/test_audit_views.py
git commit -m "feat: add AuditReport and AuditIssue API endpoints"
```

---

## Task 9: Update CLAUDE.md and final commit

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Update the folder structure section to include the new `scorers/` package:

```
backend/audits/
├── scorers/
│   ├── schemas.py          # shared Pydantic models
│   ├── claude_client.py    # retry wrapper + structured JSON logging
│   ├── seo.py / tech.py    # deterministic scorers
│   └── conversion.py / content.py / trust.py  # LLM scorers
├── scraper.py
├── tasks.py
├── serializers.py
└── views.py
```

Mark Phase 3 as complete in the checklist:

```
- [x] Phase 3 — Audit Engine (deterministic + LLM scoring, run_audit task, report API)
```

Add to Key Architectural Decisions:

```
- **scorers/ package** — five independent scorer modules; scorers have no Celery/ORM knowledge, each takes a ScrapedPage and returns a Pydantic CategoryResult
- **claude_client.py** — single entry point for all Claude calls; retries up to 3 times, logs every attempt as a JSON line (model, tokens, latency, cost, prompt_version)
- **Celery chain** — scrape_website chains into run_audit on success; job stays 'running' through both tasks, set to 'complete' only after auditing finishes
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — Phase 3 complete"
```
