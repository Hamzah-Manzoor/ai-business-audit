# Phase 2 — Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a business URL, scrape up to 5 pages and save structured `ScrapedPage` records; expose REST endpoints to trigger and poll the job.

**Architecture:** A single `scrape_website` Celery task discovers URLs (sitemap first, homepage links fallback), scrapes each page with Playwright, parses HTML with BeautifulSoup, and persists `ScrapedPage` records. Per-page errors are caught and logged so one bad URL doesn't abort the whole job. DRF views wire `POST /api/businesses/:id/audit/` and `GET /api/audits/:id/status/` to trigger and poll the job.

**Tech Stack:** Django 4.2, DRF 3.14, Celery 5.3, Playwright 1.44, BeautifulSoup4 4.12, lxml 5.2, requests 2.32, PostgreSQL 15

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/requirements.txt` | Add scraping + HTTP deps |
| Modify | `backend/Dockerfile` | Install Playwright Chromium |
| Modify | `backend/audits/models.py` | Add `image_alts` field |
| Create | `backend/audits/migrations/0003_scrapedpage_image_alts.py` | Schema migration |
| Create | `backend/audits/serializers.py` | `BusinessSerializer`, `AuditJobStatusSerializer` |
| Create | `backend/audits/views.py` | 4 API views |
| Modify | `backend/audits/urls.py` | Wire the 4 endpoints |
| Create | `backend/audits/scraper.py` | Pure extraction logic (no Celery, no DB) |
| Create | `backend/audits/tasks.py` | `scrape_website` Celery task |
| Create | `backend/audits/tests/test_serializers.py` | Serializer tests |
| Create | `backend/audits/tests/test_views.py` | View tests |
| Create | `backend/audits/tests/test_scraper.py` | Scraper unit tests |
| Create | `backend/audits/tests/test_tasks.py` | Task integration tests |
| Modify | `CLAUDE.md` | Mark Phase 2 complete |

---

## Task 1: Add Dependencies and Update Dockerfile

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Add scraping dependencies to requirements.txt**

Replace the entire contents of `backend/requirements.txt` with:

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
```

- [ ] **Step 2: Update Dockerfile to install Playwright Chromium**

Replace the contents of `backend/Dockerfile` with:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "feat: add playwright, beautifulsoup4, lxml, requests dependencies"
```

---

## Task 2: Add image_alts Field to ScrapedPage

**Files:**
- Modify: `backend/audits/models.py`
- Create: `backend/audits/migrations/0003_scrapedpage_image_alts.py` (auto-generated)
- Modify: `backend/audits/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/audits/tests/test_models.py` inside the `ScrapedPageModelTest` class:

```python
    def test_image_alts_defaults_to_empty_list(self):
        page = ScrapedPage.objects.create(
            business=self.business, audit_job=self.job,
            url='https://acme.com',
        )
        self.assertEqual(page.image_alts, [])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec backend python manage.py test audits.tests.test_models.ScrapedPageModelTest.test_image_alts_defaults_to_empty_list
```

Expected: `AttributeError` or `FieldError` — `image_alts` does not exist yet.

- [ ] **Step 3: Add image_alts field to ScrapedPage model**

In `backend/audits/models.py`, add `image_alts` to `ScrapedPage` after the `internal_links` field:

```python
    internal_links = models.JSONField(default=list)
    image_alts = models.JSONField(default=list)
    load_time_ms = models.IntegerField(null=True, blank=True)
```

- [ ] **Step 4: Generate and apply migration**

```bash
docker compose exec backend python manage.py makemigrations audits --name scrapedpage_image_alts
docker compose exec backend python manage.py migrate
```

Expected output ends with: `Applying audits.0003_scrapedpage_image_alts... OK`

- [ ] **Step 5: Run test to verify it passes**

```bash
docker compose exec backend python manage.py test audits.tests.test_models
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/audits/models.py backend/audits/migrations/0003_scrapedpage_image_alts.py backend/audits/tests/test_models.py
git commit -m "feat: add image_alts field to ScrapedPage"
```

---

## Task 3: Create Serializers

**Files:**
- Create: `backend/audits/serializers.py`
- Create: `backend/audits/tests/test_serializers.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_serializers.py`:

```python
from django.test import TestCase
from audits.models import Business, AuditJob
from audits.serializers import BusinessSerializer, AuditJobStatusSerializer


class BusinessSerializerTest(TestCase):
    def test_serializes_required_fields(self):
        business = Business.objects.create(name='Acme', url='https://acme.com', industry_type='SaaS')
        data = BusinessSerializer(business).data
        self.assertEqual(data['name'], 'Acme')
        self.assertEqual(data['url'], 'https://acme.com')
        self.assertEqual(data['industry_type'], 'SaaS')
        self.assertIn('id', data)
        self.assertIn('created_at', data)

    def test_valid_data_deserializes(self):
        serializer = BusinessSerializer(data={'name': 'Acme', 'url': 'https://acme.com'})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_url_is_invalid(self):
        serializer = BusinessSerializer(data={'name': 'Acme'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)

    def test_missing_name_is_invalid(self):
        serializer = BusinessSerializer(data={'url': 'https://acme.com'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)


class AuditJobStatusSerializerTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business, status='running')

    def test_serializes_status_fields(self):
        data = AuditJobStatusSerializer(self.job).data
        self.assertEqual(data['id'], self.job.id)
        self.assertEqual(data['status'], 'running')
        self.assertIn('triggered_at', data)
        self.assertIsNone(data['completed_at'])
        self.assertEqual(data['error_message'], '')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_serializers
```

Expected: `ImportError` — `audits.serializers` does not exist yet.

- [ ] **Step 3: Create serializers.py**

Create `backend/audits/serializers.py`:

```python
from rest_framework import serializers
from .models import Business, AuditJob


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_serializers
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/audits/serializers.py backend/audits/tests/test_serializers.py
git commit -m "feat: add BusinessSerializer and AuditJobStatusSerializer"
```

---

## Task 4: Business API Views and URL Routing

**Files:**
- Create: `backend/audits/views.py`
- Modify: `backend/audits/urls.py`
- Create: `backend/audits/tests/test_views.py`

- [ ] **Step 1: Write the failing tests for business endpoints**

Create `backend/audits/tests/test_views.py`:

```python
import json
from unittest.mock import patch
from django.test import TestCase
from audits.models import Business, AuditJob


class BusinessListCreateViewTest(TestCase):
    def test_create_business_returns_201(self):
        response = self.client.post(
            '/api/businesses/',
            data=json.dumps({'name': 'Acme', 'url': 'https://acme.com', 'industry_type': 'SaaS'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Acme')
        self.assertIn('id', response.json())

    def test_create_business_missing_url_returns_400(self):
        response = self.client.post(
            '/api/businesses/',
            data=json.dumps({'name': 'Acme'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_list_businesses_returns_200(self):
        Business.objects.create(name='Acme', url='https://acme.com')
        Business.objects.create(name='Beta', url='https://beta.com')
        response = self.client.get('/api/businesses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_list_businesses_empty_returns_200(self):
        response = self.client.get('/api/businesses/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class BusinessDetailViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    def test_get_existing_business_returns_200(self):
        response = self.client.get(f'/api/businesses/{self.business.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Acme')

    def test_get_missing_business_returns_404(self):
        response = self.client.get('/api/businesses/9999/')
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_views.BusinessListCreateViewTest audits.tests.test_views.BusinessDetailViewTest
```

Expected: 404 responses (no URL routes registered yet).

- [ ] **Step 3: Create views.py with business views**

Create `backend/audits/views.py`:

```python
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditJob, Business
from .serializers import AuditJobStatusSerializer, BusinessSerializer
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
```

- [ ] **Step 4: Wire URLs**

Replace the entire contents of `backend/audits/urls.py` with:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('businesses/', views.BusinessListCreateView.as_view(), name='business-list'),
    path('businesses/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('businesses/<int:pk>/audit/', views.AuditTriggerView.as_view(), name='audit-trigger'),
    path('audits/<int:pk>/status/', views.AuditStatusView.as_view(), name='audit-status'),
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_views.BusinessListCreateViewTest audits.tests.test_views.BusinessDetailViewTest
```

Expected: all 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/audits/views.py backend/audits/urls.py backend/audits/tests/test_views.py
git commit -m "feat: add business list, create, and detail API endpoints"
```

---

## Task 5: Audit Trigger and Status Endpoints

**Files:**
- Modify: `backend/audits/tests/test_views.py` (add new test classes)
- No views changes needed — already written in Task 4

The views for `AuditTriggerView` and `AuditStatusView` were created in Task 4. This task adds their tests. Note: `AuditTriggerView` imports `scrape_website` from `tasks.py`, which doesn't exist yet. We mock it in these tests.

- [ ] **Step 1: Write the failing tests for audit endpoints**

Append to `backend/audits/tests/test_views.py`:

```python

class AuditTriggerViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    @patch('audits.views.scrape_website')
    def test_creates_audit_job_and_dispatches_task(self, mock_task):
        response = self.client.post(f'/api/businesses/{self.business.id}/audit/')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'pending')
        self.assertIn('audit_job_id', data)
        mock_task.delay.assert_called_once_with(data['audit_job_id'])

    @patch('audits.views.scrape_website')
    def test_audit_trigger_missing_business_returns_404(self, mock_task):
        response = self.client.post('/api/businesses/9999/audit/')
        self.assertEqual(response.status_code, 404)
        mock_task.delay.assert_not_called()


class AuditStatusViewTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business, status='running')

    def test_returns_job_status(self):
        response = self.client.get(f'/api/audits/{self.job.id}/status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'running')
        self.assertEqual(data['id'], self.job.id)

    def test_missing_job_returns_404(self):
        response = self.client.get('/api/audits/9999/status/')
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Create a stub tasks.py so imports don't fail**

Create `backend/audits/tasks.py`:

```python
from celery import shared_task


@shared_task
def scrape_website(audit_job_id: int):
    pass
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_views
```

Expected: all 10 tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/audits/tasks.py backend/audits/tests/test_views.py
git commit -m "feat: add audit trigger and status endpoints"
```

---

## Task 6: Create scraper.py — Pure Extraction Logic

**Files:**
- Create: `backend/audits/scraper.py`
- Create: `backend/audits/tests/test_scraper.py`

This module contains zero Celery, zero DB, zero Playwright — pure functions that take strings and return dicts. This makes them fast to test.

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_scraper.py`:

```python
from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.scraper import discover_urls_from_sitemap, extract_same_domain_links, extract_page_data

SAMPLE_HTML = """
<html>
<head>
    <title>  Acme Corp  </title>
    <meta name="description" content="We make great products">
</head>
<body>
    <h1>Welcome to Acme</h1>
    <h2>Our Products</h2>
    <h2>Our Team</h2>
    <img src="logo.png" alt="Acme Logo">
    <img src="hero.png">
    <a href="https://acme.com/about">About</a>
    <a href="https://acme.com/pricing">Pricing</a>
    <a href="https://other.com/page">External</a>
    <a href="/contact">Contact</a>
    <p>We make great products for businesses.</p>
    <script>var x = 1; console.log("hidden");</script>
    <style>.hidden { display: none; }</style>
</body>
</html>
"""

SAMPLE_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://acme.com/</loc></url>
    <url><loc>https://acme.com/about</loc></url>
    <url><loc>https://acme.com/pricing</loc></url>
    <url><loc>https://acme.com/contact</loc></url>
    <url><loc>https://acme.com/blog</loc></url>
    <url><loc>https://other.com/external</loc></url>
</urlset>
"""


class ExtractPageDataTest(TestCase):
    def test_extracts_title_stripped(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['meta_title'], 'Acme Corp')

    def test_extracts_meta_description(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['meta_description'], 'We make great products')

    def test_extracts_all_h1_tags(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['h1_tags'], ['Welcome to Acme'])

    def test_extracts_all_h2_tags(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['h2_tags'], ['Our Products', 'Our Team'])

    def test_extracts_image_alts_including_empty_string(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertEqual(data['image_alts'], ['Acme Logo', ''])

    def test_internal_links_excludes_external(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/about', data['internal_links'])
        self.assertIn('https://acme.com/pricing', data['internal_links'])
        self.assertNotIn('https://other.com/page', data['internal_links'])

    def test_relative_links_resolved_to_absolute(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/contact', data['internal_links'])

    def test_extracted_text_excludes_script_content(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertNotIn('var x = 1', data['extracted_text'])
        self.assertNotIn('console.log', data['extracted_text'])

    def test_extracted_text_excludes_style_content(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertNotIn('.hidden', data['extracted_text'])

    def test_extracted_text_includes_body_text(self):
        data = extract_page_data(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('We make great products for businesses', data['extracted_text'])

    def test_missing_title_returns_empty_string(self):
        html = '<html><body><p>No title</p></body></html>'
        data = extract_page_data(html, 'https://acme.com')
        self.assertEqual(data['meta_title'], '')

    def test_missing_description_returns_empty_string(self):
        html = '<html><head><title>T</title></head><body></body></html>'
        data = extract_page_data(html, 'https://acme.com')
        self.assertEqual(data['meta_description'], '')


class DiscoverUrlsFromSitemapTest(TestCase):
    @patch('audits.scraper.requests.get')
    def test_returns_same_domain_urls_excluding_homepage(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertIn('https://acme.com/about', result)
        self.assertIn('https://acme.com/pricing', result)
        self.assertNotIn('https://other.com/external', result)

    @patch('audits.scraper.requests.get')
    def test_excludes_homepage_from_results(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertNotIn('https://acme.com/', result)
        self.assertNotIn('https://acme.com', result)

    @patch('audits.scraper.requests.get')
    def test_caps_results_at_four(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=SAMPLE_SITEMAP)
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertLessEqual(len(result), 4)

    @patch('audits.scraper.requests.get')
    def test_returns_empty_on_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404, text='')
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertEqual(result, [])

    @patch('audits.scraper.requests.get')
    def test_returns_empty_on_connection_error(self, mock_get):
        mock_get.side_effect = Exception('Connection refused')
        result = discover_urls_from_sitemap('https://acme.com')
        self.assertEqual(result, [])


class ExtractSameDomainLinksTest(TestCase):
    def test_returns_same_domain_links(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/about', result)
        self.assertNotIn('https://other.com/page', result)

    def test_resolves_relative_links(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com')
        self.assertIn('https://acme.com/contact', result)

    def test_respects_limit(self):
        result = extract_same_domain_links(SAMPLE_HTML, 'https://acme.com', limit=1)
        self.assertEqual(len(result), 1)

    def test_deduplicates_links(self):
        html = '<html><body><a href="/about">A</a><a href="/about">A again</a></body></html>'
        result = extract_same_domain_links(html, 'https://acme.com')
        self.assertEqual(result.count('https://acme.com/about'), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_scraper
```

Expected: `ImportError` — `audits.scraper` does not exist yet.

- [ ] **Step 3: Create scraper.py**

Create `backend/audits/scraper.py`:

```python
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def discover_urls_from_sitemap(homepage: str) -> list:
    """Fetch sitemap.xml and return up to 4 same-domain URLs (homepage excluded)."""
    try:
        resp = requests.get(f"{homepage}/sitemap.xml", timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'lxml-xml')
        root = urlparse(homepage)
        results = []
        for loc in soup.find_all('loc'):
            url = loc.text.strip()
            parsed = urlparse(url)
            if parsed.netloc != root.netloc:
                continue
            if url.rstrip('/') == homepage.rstrip('/'):
                continue
            results.append(url)
            if len(results) >= 4:
                break
        return results
    except Exception as e:
        logger.warning(f"Sitemap fetch failed for {homepage}: {e}")
        return []


def extract_same_domain_links(html: str, base_url: str, limit: int = 4) -> list:
    """Return unique same-domain absolute links found in html, up to limit."""
    root = urlparse(base_url)
    soup = BeautifulSoup(html, 'lxml')
    seen = set()
    links = []
    for a in soup.find_all('a', href=True):
        href = urljoin(base_url, a['href'])
        parsed = urlparse(href)
        if parsed.netloc == root.netloc and href not in seen:
            seen.add(href)
            links.append(href)
            if len(links) >= limit:
                break
    return links


def extract_page_data(html: str, url: str) -> dict:
    """Parse html and return structured page data dict. No network I/O."""
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style']):
        tag.decompose()

    root = urlparse(url)
    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})

    seen_links = set()
    internal_links = []
    for a in soup.find_all('a', href=True):
        href = urljoin(url, a['href'])
        if urlparse(href).netloc == root.netloc and href not in seen_links:
            seen_links.add(href)
            internal_links.append(href)

    return {
        'meta_title': soup.title.get_text(strip=True) if soup.title else '',
        'meta_description': meta_desc_tag.get('content', '') if meta_desc_tag else '',
        'h1_tags': [h.get_text(strip=True) for h in soup.find_all('h1')],
        'h2_tags': [h.get_text(strip=True) for h in soup.find_all('h2')],
        'image_alts': [img.get('alt', '') for img in soup.find_all('img')],
        'extracted_text': ' '.join(soup.get_text(separator=' ').split()),
        'internal_links': internal_links,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_scraper
```

Expected: all 20 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/audits/scraper.py backend/audits/tests/test_scraper.py
git commit -m "feat: add scraper module with page extraction and URL discovery"
```

---

## Task 7: Implement scrape_website Celery Task

**Files:**
- Modify: `backend/audits/tasks.py`
- Create: `backend/audits/tests/test_tasks.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/audits/tests/test_tasks.py`:

```python
import time
from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.models import AuditJob, Business, ScrapedPage
from audits.tasks import scrape_website

MINIMAL_HTML = '<html><head><title>Acme</title></head><body><h1>Hello</h1></body></html>'


def _make_playwright_mock(html=MINIMAL_HTML, status_code=200, goto_raises=None):
    """Return a mock sync_playwright context that yields a usable page."""
    mock_response = MagicMock()
    mock_response.status = status_code

    mock_page = MagicMock()
    mock_page.content.return_value = html
    if goto_raises:
        mock_page.goto.side_effect = goto_raises
    else:
        mock_page.goto.return_value = mock_response

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_p)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    return mock_ctx


class ScrapeWebsiteTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=self.business)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_marks_job_running_then_complete(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertIsNotNone(self.job.completed_at)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_saves_scraped_page_record(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        pages = ScrapedPage.objects.filter(audit_job=self.job)
        self.assertEqual(pages.count(), 1)
        page = pages.first()
        self.assertEqual(page.url, 'https://acme.com')
        self.assertEqual(page.meta_title, 'Acme')
        self.assertEqual(page.h1_tags, ['Hello'])
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.https)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_uses_sitemap_urls_when_available(self, mock_discover, mock_playwright):
        mock_discover.return_value = ['https://acme.com/about', 'https://acme.com/pricing']
        mock_playwright.return_value = _make_playwright_mock()

        scrape_website(self.job.id)

        urls_scraped = list(ScrapedPage.objects.filter(audit_job=self.job).values_list('url', flat=True))
        self.assertIn('https://acme.com', urls_scraped)
        self.assertIn('https://acme.com/about', urls_scraped)
        self.assertIn('https://acme.com/pricing', urls_scraped)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_marks_failed_when_all_pages_fail(self, mock_discover, mock_playwright):
        mock_discover.return_value = []
        mock_playwright.return_value = _make_playwright_mock(goto_raises=Exception('Timeout'))

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertIn('Timeout', self.job.error_message)

    def test_returns_early_for_nonexistent_job(self):
        # Should not raise — just log and return
        scrape_website(99999)

    @patch('audits.tasks.sync_playwright')
    @patch('audits.tasks.discover_urls_from_sitemap')
    def test_continues_after_single_page_failure(self, mock_discover, mock_playwright):
        mock_discover.return_value = ['https://acme.com/about']

        mock_response = MagicMock()
        mock_response.status = 200
        mock_page = MagicMock()
        mock_page.content.return_value = MINIMAL_HTML
        call_count = {'n': 0}

        def goto_side_effect(url, **kwargs):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise Exception('First page failed')
            return mock_response

        mock_page.goto.side_effect = goto_side_effect
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_p)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_playwright.return_value = mock_ctx

        scrape_website(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')
        self.assertEqual(ScrapedPage.objects.filter(audit_job=self.job).count(), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_tasks
```

Expected: tests fail — `scrape_website` is a stub that does nothing.

- [ ] **Step 3: Implement scrape_website task**

Replace the contents of `backend/audits/tasks.py` with:

```python
import logging
import time
from urllib.parse import urlparse

from celery import shared_task
from django.utils import timezone
from playwright.sync_api import sync_playwright

from .scraper import discover_urls_from_sitemap, extract_page_data, extract_same_domain_links

logger = logging.getLogger(__name__)


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
    saved_count = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            playwright_page = browser.new_page()

            sitemap_urls = discover_urls_from_sitemap(homepage)
            if sitemap_urls:
                urls = list(dict.fromkeys([homepage] + sitemap_urls))[:5]
            else:
                playwright_page.goto(homepage, timeout=30000, wait_until='networkidle')
                homepage_html = playwright_page.content()
                fallback_links = extract_same_domain_links(homepage_html, homepage, limit=4)
                urls = list(dict.fromkeys([homepage] + fallback_links))[:5]

            for url in urls:
                try:
                    t_start = time.monotonic()
                    response = playwright_page.goto(url, timeout=30000, wait_until='networkidle')
                    load_time_ms = int((time.monotonic() - t_start) * 1000)
                    html = playwright_page.content()
                    data = extract_page_data(html, url)
                    ScrapedPage.objects.create(
                        business=business,
                        audit_job=job,
                        url=url,
                        html_content=html,
                        status_code=response.status if response else None,
                        load_time_ms=load_time_ms,
                        https=url.startswith('https://'),
                        **data,
                    )
                    saved_count += 1
                    logger.info(f"Scraped {url} (job={audit_job_id})")
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Failed to scrape {url} (job={audit_job_id}): {e}")

            browser.close()

    except Exception as e:
        last_error = str(e)
        logger.error(f"Fatal scrape error for job {audit_job_id}: {e}")

    if saved_count > 0:
        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
    else:
        job.status = 'failed'
        job.error_message = last_error or 'No pages could be scraped'
        job.save(update_fields=['status', 'error_message'])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_tasks
```

Expected: all 6 tests pass.

- [ ] **Step 5: Run the full test suite**

```bash
docker compose exec backend python manage.py test
```

Expected: all tests pass (models + serializers + views + scraper + tasks).

- [ ] **Step 6: Commit**

```bash
git add backend/audits/tasks.py backend/audits/tests/test_tasks.py
git commit -m "feat: implement scrape_website Celery task with per-page error isolation"
```

---

## Task 8: Rebuild Docker Images and Smoke Test

**No code changes — verification only.**

- [ ] **Step 1: Rebuild Docker images**

```bash
docker compose build
```

Expected: build completes. The Playwright install step downloads Chromium (~200MB on first build).

- [ ] **Step 2: Start all services**

```bash
docker compose up -d
```

Expected: all 5 services start (`db`, `redis`, `backend`, `celery`, `frontend`).

- [ ] **Step 3: Apply migrations**

```bash
docker compose exec backend python manage.py migrate
```

Expected: `Applying audits.0003_scrapedpage_image_alts... OK`

- [ ] **Step 4: Create a test business**

```bash
curl -s -X POST http://localhost:8000/api/businesses/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Example", "url": "https://example.com", "industry_type": "Other"}' | python3 -m json.tool
```

Expected: JSON response with `id` field. Note the `id` value.

- [ ] **Step 5: Trigger an audit (replace 1 with the id from step 4)**

```bash
curl -s -X POST http://localhost:8000/api/businesses/1/audit/ | python3 -m json.tool
```

Expected:
```json
{
    "audit_job_id": 1,
    "status": "pending"
}
```

Note the `audit_job_id`.

- [ ] **Step 6: Poll status until complete (replace 1 with audit_job_id)**

```bash
curl -s http://localhost:8000/api/audits/1/status/ | python3 -m json.tool
```

Expected within ~30s:
```json
{
    "id": 1,
    "status": "complete",
    "triggered_at": "...",
    "completed_at": "...",
    "error_message": ""
}
```

- [ ] **Step 7: Verify ScrapedPage records in Django admin**

Open http://localhost:8000/admin and navigate to Scraped Pages. Confirm ≥1 record exists with `meta_title`, `h1_tags`, `load_time_ms`, and `status_code` populated.

- [ ] **Step 8: Commit smoke test evidence (optional)**

No code changes — just confirm the done criteria is met.

---

## Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Mark Phase 2 complete and update the phase checklist**

In `CLAUDE.md`, update the phase completion status section:

```markdown
## Phase Completion Status
- [x] Phase 1 — Foundation (skeleton, models, Docker, health check)
- [x] Phase 2 — Scraper (Celery task, Playwright + BS4, 5-page crawl, REST endpoints)
- [ ] Phase 3 — Audit Engine
- [ ] Phase 4 — RAG Knowledge System
- [ ] Phase 5 — Decision Engine
- [ ] Phase 6 — Dashboard
```

Also add to the **Folder Structure** section any new files created:
```
│   ├── audits/
│   │   ├── scraper.py    # pure page extraction logic (no Celery/DB)
│   │   ├── tasks.py      # scrape_website Celery task
│   │   ├── serializers.py
│   │   └── views.py
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — Phase 2 complete"
```
