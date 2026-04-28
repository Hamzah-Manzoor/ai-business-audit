# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the full project skeleton — Django + DRF backend with all 7 data models, Next.js frontend, and Docker Compose for all services (Django, Postgres+pgvector, Redis, Next.js) with a `/api/health/` endpoint.

**Architecture:** Django serves a REST API at `/api/` backed by PostgreSQL (pgvector extension enabled for Phase 4 embeddings) and Redis (Celery broker for Phase 2+). Next.js runs as a separate container. All services orchestrated by Docker Compose. Phase 1 contains no business logic — models, admin, health check, and infrastructure only.

**Tech Stack:** Python 3.11, Django 4.2, Django REST Framework 3.14, PostgreSQL 15 + pgvector, Redis 7, Celery 5.3, Next.js 14 (App Router), TypeScript, Docker Compose v2

---

## File Structure

**Root:**
- `CLAUDE.md` — project source of truth
- `.gitignore`
- `.env.example` — env var names, no values
- `.env` — local dev values (gitignored)
- `docker-compose.yml`

**Backend:**
- `backend/Dockerfile`
- `backend/.dockerignore`
- `backend/requirements.txt`
- `backend/manage.py`
- `backend/config/__init__.py`
- `backend/config/settings.py` — all settings via env vars
- `backend/config/urls.py` — root URL conf
- `backend/config/wsgi.py`
- `backend/config/asgi.py`
- `backend/core/__init__.py`
- `backend/core/apps.py`
- `backend/core/views.py` — health check view
- `backend/core/urls.py`
- `backend/core/tests/__init__.py`
- `backend/core/tests/test_health.py`
- `backend/audits/__init__.py`
- `backend/audits/apps.py`
- `backend/audits/models.py` — all 7 data models
- `backend/audits/admin.py`
- `backend/audits/urls.py` — empty for now
- `backend/audits/migrations/__init__.py`
- `backend/audits/migrations/0001_initial.py` — auto-generated
- `backend/audits/migrations/0002_enable_pgvector.py` — enable vector extension
- `backend/audits/tests/__init__.py`
- `backend/audits/tests/test_models.py`

**Frontend:**
- `frontend/Dockerfile`
- `frontend/.dockerignore`
- `frontend/package.json`
- `frontend/next.config.js`
- `frontend/tsconfig.json`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`

---

## Task 1: Root scaffolding — .gitignore, .env files, CLAUDE.md

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.env`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create .gitignore**

```
# Environment
.env
*.env.local

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.venv/
venv/

# Django
*.sqlite3
media/
staticfiles/

# Node
node_modules/
.next/
out/
npm-debug.log*

# Docker volumes
.docker/

# IDE
.vscode/
.idea/
*.swp
.DS_Store
```

- [ ] **Step 2: Create .env.example**

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

- [ ] **Step 3: Create .env (local dev — gitignored)**

```
DJANGO_SECRET_KEY=local-dev-secret-key-change-in-production
DATABASE_URL=postgres://postgres:postgres@db:5432/ai_business_audit
REDIS_URL=redis://redis:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend
ANTHROPIC_API_KEY=placeholder
OPENAI_API_KEY=placeholder
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

- [ ] **Step 4: Create CLAUDE.md**

```markdown
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
├── backend/          # Django project
│   ├── config/       # settings, urls, wsgi
│   ├── core/         # health check
│   └── audits/       # all data models, business logic
├── frontend/         # Next.js app
└── docker-compose.yml
```

## Environment Variables
See `.env.example` for all required variables. Never commit `.env`.

## How to Run Locally
```bash
cp .env.example .env   # fill in real values
docker compose up --build
```
- Django API: http://localhost:8000
- Django Admin: http://localhost:8000/admin (create superuser first)
- Next.js: http://localhost:3000
- Health check: http://localhost:8000/api/health/

Create a Django superuser:
```bash
docker compose exec backend python manage.py createsuperuser
```

## Phase Completion Status
- [x] Phase 1 — Foundation (skeleton, models, Docker, health check)
- [ ] Phase 2 — Scraper
- [ ] Phase 3 — Audit Engine
- [ ] Phase 4 — RAG Knowledge System
- [ ] Phase 5 — Decision Engine
- [ ] Phase 6 — Dashboard

## Key Architectural Decisions
- **pgvector in Postgres** — keeps vector search co-located with relational data, avoids a separate vector DB service
- **Celery + Redis** — decouples long-running scrape/audit jobs from the HTTP request cycle
- **Separate Django apps** — `core` for infrastructure (health), `audits` for all domain models/logic
- **django-environ** — all secrets via env vars, 12-factor compliant

## Known Issues / TODOs
- Phase 1 only: ANTHROPIC_API_KEY and OPENAI_API_KEY are placeholders
- Celery worker defined in docker-compose but has no tasks until Phase 2
```

- [ ] **Step 5: Commit**

```bash
git init
git add .gitignore .env.example CLAUDE.md
git commit -m "chore: initial project scaffolding"
```

---

## Task 2: Django project setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/manage.py`
- Create: `backend/config/__init__.py`
- Create: `backend/config/settings.py`
- Create: `backend/config/urls.py`
- Create: `backend/config/wsgi.py`
- Create: `backend/config/asgi.py`

- [ ] **Step 1: Create backend/requirements.txt**

```
Django==4.2.13
djangorestframework==3.14.0
psycopg2-binary==2.9.9
django-environ==0.11.2
pgvector==0.3.3
celery==5.3.6
redis==5.0.4
django-cors-headers==4.3.1
```

- [ ] **Step 2: Create backend/manage.py**

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Create backend/config/__init__.py** (empty)

- [ ] **Step 4: Create backend/config/settings.py**

```python
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(BASE_DIR.parent / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY', default='dev-secret-key-change-me')
DEBUG = env('DEBUG', default=True)
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
    'audits',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://postgres:postgres@localhost:5432/ai_business_audit',
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
```

- [ ] **Step 5: Create backend/config/urls.py**

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/', include('audits.urls')),
]
```

- [ ] **Step 6: Create backend/config/wsgi.py**

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
```

- [ ] **Step 7: Create backend/config/asgi.py**

```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_asgi_application()
```

---

## Task 3: Core app — health check endpoint (TDD)

**Files:**
- Create: `backend/core/__init__.py`
- Create: `backend/core/apps.py`
- Create: `backend/core/views.py`
- Create: `backend/core/urls.py`
- Create: `backend/core/tests/__init__.py`
- Create: `backend/core/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `backend/core/tests/__init__.py` (empty).

Create `backend/core/tests/test_health.py`:

```python
from django.test import TestCase
from django.urls import reverse


class HealthCheckTestCase(TestCase):
    def test_health_returns_200(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok_status(self):
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertEqual(data['status'], 'ok')
```

- [ ] **Step 2: Create stub files so Django can discover the test**

Create `backend/core/__init__.py` (empty).

Create `backend/core/apps.py`:
```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
```

Create `backend/core/views.py` (stub — test will fail at this point):
```python
# stub
```

Create `backend/core/urls.py` (stub):
```python
from django.urls import path
urlpatterns = []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend
pip install -r requirements.txt
python manage.py test core.tests.test_health -v 2
```

Expected: FAIL — 404 because the URL doesn't exist yet.

- [ ] **Step 4: Implement the health check view**

Replace `backend/core/views.py`:
```python
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def health_check(request):
    return Response({'status': 'ok'})
```

Replace `backend/core/urls.py`:
```python
from django.urls import path
from core.views import health_check

urlpatterns = [
    path('health/', health_check, name='health-check'),
]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python manage.py test core.tests.test_health -v 2
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat: add core app with health check endpoint"
```

---

## Task 4: Audits app — all 7 data models

**Files:**
- Create: `backend/audits/__init__.py`
- Create: `backend/audits/apps.py`
- Create: `backend/audits/models.py`
- Create: `backend/audits/urls.py`
- Create: `backend/audits/migrations/__init__.py`
- Create: `backend/audits/migrations/0001_pgvector_extension.py`
- Create: `backend/audits/tests/__init__.py`
- Create: `backend/audits/tests/test_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `backend/audits/tests/__init__.py` (empty).

Create `backend/audits/tests/test_models.py`:
```python
from django.test import TestCase
from audits.models import (
    Business, AuditJob, AuditReport, AuditIssue,
    Recommendation, KnowledgeDoc, ScrapedPage,
)


class BusinessModelTest(TestCase):
    def test_create_business(self):
        b = Business.objects.create(name='Acme', url='https://acme.com', industry_type='SaaS')
        self.assertEqual(str(b), 'Acme')
        self.assertIsNotNone(b.created_at)


class AuditJobModelTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')

    def test_default_status_is_pending(self):
        job = AuditJob.objects.create(business=self.business)
        self.assertEqual(job.status, 'pending')

    def test_str_includes_status(self):
        job = AuditJob.objects.create(business=self.business)
        self.assertIn('pending', str(job))


class AuditReportModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=business)

    def test_create_report(self):
        report = AuditReport.objects.create(
            audit_job=self.job, overall_score=75,
            seo_score=80, conversion_score=70,
            content_score=75, tech_score=85, trust_score=60,
        )
        self.assertEqual(report.overall_score, 75)


class AuditIssueModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        job = AuditJob.objects.create(business=business)
        self.report = AuditReport.objects.create(audit_job=job, overall_score=50)

    def test_create_issue(self):
        issue = AuditIssue.objects.create(
            report=self.report, category='seo', severity='critical',
            title='Missing H1', description='No H1 tag found.',
            parameter_key='h1_exists', score=0,
        )
        self.assertIn('critical', str(issue).lower())


class RecommendationModelTest(TestCase):
    def setUp(self):
        business = Business.objects.create(name='Acme', url='https://acme.com')
        job = AuditJob.objects.create(business=business)
        self.report = AuditReport.objects.create(audit_job=job, overall_score=50)

    def test_create_recommendation(self):
        rec = Recommendation.objects.create(
            report=self.report, priority_score=9.5,
            effort='low', impact='high',
            title='Add H1 tag', rationale='H1 improves SEO.',
        )
        self.assertEqual(rec.effort, 'low')


class KnowledgeDocModelTest(TestCase):
    def test_create_knowledge_doc(self):
        doc = KnowledgeDoc.objects.create(
            title='CTA Best Practices', category='conversion',
            content='Use action verbs in CTAs.', source='internal',
        )
        self.assertEqual(str(doc), 'CTA Best Practices')
        self.assertIsNone(doc.embedding)


class ScrapedPageModelTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Acme', url='https://acme.com')
        self.job = AuditJob.objects.create(business=self.business)

    def test_create_scraped_page(self):
        page = ScrapedPage.objects.create(
            business=self.business, audit_job=self.job,
            url='https://acme.com', https=True, status_code=200,
        )
        self.assertIn('acme.com', str(page))
```

- [ ] **Step 2: Create app skeleton so Django can discover it**

Create `backend/audits/__init__.py` (empty).

Create `backend/audits/apps.py`:
```python
from django.apps import AppConfig


class AuditsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audits'
```

Create `backend/audits/urls.py` (empty for Phase 1):
```python
from django.urls import path

urlpatterns = []
```

Create `backend/audits/migrations/__init__.py` (empty).

- [ ] **Step 3: Run tests to confirm they fail (models don't exist yet)**

```bash
python manage.py test audits.tests.test_models -v 2
```

Expected: ImportError or ModuleNotFoundError for audits.models

- [ ] **Step 4: Create the pgvector extension migration**

Create `backend/audits/migrations/0001_pgvector_extension.py`:
```python
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS vector;',
            reverse_sql='DROP EXTENSION IF EXISTS vector;',
        ),
    ]
```

- [ ] **Step 5: Create all 7 models in audits/models.py**

Create `backend/audits/models.py`:
```python
from django.db import models
from pgvector.django import VectorField


class Business(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    industry_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'businesses'

    def __str__(self):
        return self.name


class AuditJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='audit_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    triggered_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"AuditJob {self.id} ({self.status}) for {self.business}"


class AuditReport(models.Model):
    audit_job = models.OneToOneField(AuditJob, on_delete=models.CASCADE, related_name='report')
    overall_score = models.IntegerField(default=0)
    seo_score = models.IntegerField(default=0)
    conversion_score = models.IntegerField(default=0)
    content_score = models.IntegerField(default=0)
    tech_score = models.IntegerField(default=0)
    trust_score = models.IntegerField(default=0)
    raw_llm_response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report for Job {self.audit_job_id} (score: {self.overall_score})"


class AuditIssue(models.Model):
    CATEGORY_CHOICES = [
        ('seo', 'SEO'),
        ('conversion', 'Conversion'),
        ('content', 'Content'),
        ('tech', 'Tech'),
        ('trust', 'Trust'),
    ]
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]
    report = models.ForeignKey(AuditReport, on_delete=models.CASCADE, related_name='issues')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    parameter_key = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.severity.upper()}: {self.title}"


class Recommendation(models.Model):
    EFFORT_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    IMPACT_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]

    report = models.ForeignKey(AuditReport, on_delete=models.CASCADE, related_name='recommendations')
    issue = models.ForeignKey(
        AuditIssue, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recommendations',
    )
    priority_score = models.FloatField(default=0.0)
    effort = models.CharField(max_length=10, choices=EFFORT_CHOICES)
    impact = models.CharField(max_length=10, choices=IMPACT_CHOICES)
    title = models.CharField(max_length=255)
    rationale = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority_score']

    def __str__(self):
        return f"Recommendation: {self.title}"


class KnowledgeDoc(models.Model):
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    content = models.TextField()
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    source = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ScrapedPage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='scraped_pages')
    audit_job = models.ForeignKey(AuditJob, on_delete=models.CASCADE, related_name='scraped_pages')
    url = models.URLField(max_length=500)
    html_content = models.TextField(blank=True)
    extracted_text = models.TextField(blank=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    h1_tags = models.JSONField(default=list)
    h2_tags = models.JSONField(default=list)
    internal_links = models.JSONField(default=list)
    load_time_ms = models.IntegerField(null=True, blank=True)
    https = models.BooleanField(default=False)
    status_code = models.IntegerField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ScrapedPage: {self.url}"
```

- [ ] **Step 6: Generate migrations**

```bash
python manage.py makemigrations audits
```

Expected: Creates `backend/audits/migrations/0002_initial.py` with all 7 models.

- [ ] **Step 7: Run tests to verify they pass (requires DB — use Docker or local Postgres)**

Tests run against the database. In Docker context they'll run during `docker compose up`. For a quick check:
```bash
python manage.py test audits.tests.test_models -v 2
```

Expected: 7 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/audits/
git commit -m "feat: add all 7 data models with pgvector extension migration"
```

---

## Task 5: Django admin registration

**Files:**
- Modify: `backend/audits/admin.py`

- [ ] **Step 1: Register all models in admin**

Create `backend/audits/admin.py`:
```python
from django.contrib import admin
from audits.models import (
    Business, AuditJob, AuditReport, AuditIssue,
    Recommendation, KnowledgeDoc, ScrapedPage,
)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'industry_type', 'created_at')
    search_fields = ('name', 'url')


@admin.register(AuditJob)
class AuditJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'status', 'triggered_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('business__name',)


@admin.register(AuditReport)
class AuditReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'audit_job', 'overall_score', 'seo_score', 'conversion_score', 'created_at')


@admin.register(AuditIssue)
class AuditIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'severity', 'score', 'created_at')
    list_filter = ('category', 'severity')
    search_fields = ('title', 'parameter_key')


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority_score', 'effort', 'impact', 'created_at')
    list_filter = ('effort', 'impact')


@admin.register(KnowledgeDoc)
class KnowledgeDocAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'source', 'created_at')
    list_filter = ('category',)
    search_fields = ('title', 'content')


@admin.register(ScrapedPage)
class ScrapedPageAdmin(admin.ModelAdmin):
    list_display = ('url', 'business', 'https', 'status_code', 'load_time_ms', 'scraped_at')
    list_filter = ('https',)
    search_fields = ('url',)
```

- [ ] **Step 2: Commit**

```bash
git add backend/audits/admin.py
git commit -m "feat: register all models in Django admin"
```

---

## Task 6: Next.js frontend setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/.dockerignore`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/page.tsx`

- [ ] **Step 1: Create frontend/package.json**

```json
{
  "name": "ai-business-audit-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "eslint": "^8",
    "eslint-config-next": "14.2.3"
  }
}
```

- [ ] **Step 2: Create frontend/next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
};

module.exports = nextConfig;
```

- [ ] **Step 3: Create frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{"name": "next"}],
    "paths": {"@/*": ["./src/*"]}
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create frontend/.dockerignore**

```
node_modules
.next
.git
*.md
```

- [ ] **Step 5: Create frontend/src/app/layout.tsx**

```tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI Business Audit',
  description: 'AI-powered business website audit platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Create frontend/src/app/page.tsx**

```tsx
export default function HomePage() {
  return (
    <main>
      <h1>AI Business Audit</h1>
      <p>Dashboard coming in Phase 6.</p>
    </main>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: add Next.js frontend skeleton"
```

---

## Task 7: Docker Compose — all services

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create backend/.dockerignore**

```
__pycache__
*.pyc
*.pyo
.git
.env
*.md
```

- [ ] **Step 2: Create backend/Dockerfile**

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

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 3: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
version: '3.9'

services:
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: ai_business_audit
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    command: >
      sh -c "python manage.py migrate &&
             python manage.py runserver 0.0.0.0:8000"
    volumes:
      - ./backend:/app
      - ./.env:/app/../.env:ro
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings

  celery:
    build: ./backend
    command: celery -A config worker -l info
    volumes:
      - ./backend:/app
      - ./.env:/app/../.env:ro
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

volumes:
  postgres_data:
```

- [ ] **Step 5: Add celery app to Django config**

Create `backend/config/celery.py`:
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

Update `backend/config/__init__.py`:
```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore backend/config/celery.py backend/config/__init__.py frontend/Dockerfile docker-compose.yml
git commit -m "feat: add Docker Compose with Django, Postgres+pgvector, Redis, Celery, Next.js"
```

---

## Task 8: End-to-end verification

- [ ] **Step 1: Build and start all services**

```bash
docker compose up --build
```

Expected: All 5 services start (db, redis, backend, celery, frontend).
Backend output should include:
```
Applying audits.0001_pgvector_extension... OK
Applying audits.0002_initial... OK
```

- [ ] **Step 2: Verify health check endpoint**

```bash
curl http://localhost:8000/api/health/
```

Expected:
```json
{"status": "ok"}
```

- [ ] **Step 3: Verify Django admin is accessible**

Open http://localhost:8000/admin/ in a browser.
Expected: Django admin login page loads.

- [ ] **Step 4: Create a superuser and verify all models appear in admin**

```bash
docker compose exec backend python manage.py createsuperuser
```

Log in to http://localhost:8000/admin/ and confirm all 7 models are listed under AUDITS.

- [ ] **Step 5: Verify frontend is accessible**

Open http://localhost:3000 in a browser.
Expected: Page loads with "AI Business Audit" heading.

- [ ] **Step 6: Final commit and CLAUDE.md update**

CLAUDE.md is already populated (Task 1). No further update needed for Phase 1.

```bash
git add .
git commit -m "feat: phase 1 complete — foundation with all services running"
```

---

## Self-Review

**Spec coverage check against REQUIREMENTS.md Phase 1:**
- [x] Django project setup with DRF — Task 2
- [x] Next.js project setup (App Router) — Task 6
- [x] Docker Compose: Django + Postgres + Redis + Next.js — Task 7
- [x] pgvector extension enabled in Postgres — Task 4 (migration) + docker-compose pgvector image
- [x] All data models created and migrated — Task 4 (7 models)
- [x] Django admin registered for all models — Task 5
- [x] Health check endpoint GET /api/health/ — Task 3
- [x] CLAUDE.md created and populated — Task 1

**Placeholder scan:** None found. All steps contain actual code.

**Type consistency check:**
- `VectorField(dimensions=1536)` — consistent in models.py and test
- `AuditJob.status` default `'pending'` — consistent in model and test
- `Recommendation.ordering = ['-priority_score']` — consistent with float field name
