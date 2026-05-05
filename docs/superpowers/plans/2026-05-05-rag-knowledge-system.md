# Phase 4 — RAG Knowledge System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a RAG knowledge base so the system can retrieve best-practice context for any audit issue via pgvector cosine similarity search.

**Architecture:** Six markdown files in `/knowledge_base/` are embedded via OpenAI `text-embedding-3-small` and stored in the existing `KnowledgeDoc` model. A `retrieve_similar_docs()` function in `audits/rag/retrieval.py` accepts an issue description and returns the top 3 matching docs. A management command and a `POST /api/knowledge/seed/` endpoint both trigger seeding via a shared helper.

**Tech Stack:** `openai` v1.x SDK, `python-frontmatter`, pgvector `CosineDistance` annotation, Django management commands, `unittest.mock.patch` for tests.

**Testing approach:** All implementation first, then tests, then run full suite.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/requirements.txt` | Add `openai`, `python-frontmatter` |
| Modify | `docker-compose.yml` | Mount `./knowledge_base` into backend + celery containers |
| Create | `knowledge_base/cta_copywriting.md` | CTA best-practice doc |
| Create | `knowledge_base/value_proposition_frameworks.md` | Value prop frameworks doc |
| Create | `knowledge_base/seo_onpage_checklist.md` | SEO on-page checklist doc |
| Create | `knowledge_base/core_web_vitals.md` | Core Web Vitals doc |
| Create | `knowledge_base/trust_signals.md` | Trust signals doc |
| Create | `knowledge_base/cro_research.md` | CRO research doc |
| Create | `backend/audits/rag/__init__.py` | Package marker |
| Create | `backend/audits/rag/openai_client.py` | `embed_text()` + `EmbeddingError` |
| Create | `backend/audits/rag/retrieval.py` | `retrieve_similar_docs()` |
| Create | `backend/audits/management/__init__.py` | Package marker |
| Create | `backend/audits/management/commands/__init__.py` | Package marker |
| Create | `backend/audits/management/commands/seed_knowledge.py` | `seed_knowledge_base()` + `Command` |
| Modify | `backend/audits/views.py` | Add `SeedKnowledgeView` |
| Modify | `backend/audits/urls.py` | Add `knowledge/seed/` route |
| Create | `backend/audits/tests/test_rag.py` | All RAG tests |

---

## Task 1: Add dependencies and docker-compose volume mount

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add Python packages to requirements.txt**

Open `backend/requirements.txt` and append these two lines:

```
openai==1.35.0
python-frontmatter==1.1.0
```

Full file after edit:
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
openai==1.35.0
python-frontmatter==1.1.0
```

- [ ] **Step 2: Mount knowledge_base into backend and celery in docker-compose.yml**

In `docker-compose.yml`, add `- ./knowledge_base:/knowledge_base` to the `volumes` list of both the `backend` and `celery` services.

`backend` service volumes after edit:
```yaml
volumes:
  - ./backend:/app
  - ./.env:/app/../.env:ro
  - ./knowledge_base:/knowledge_base
```

`celery` service volumes after edit:
```yaml
volumes:
  - ./backend:/app
  - ./.env:/app/../.env:ro
  - ./knowledge_base:/knowledge_base
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt docker-compose.yml
git commit -m "chore: add openai + python-frontmatter deps, mount knowledge_base in Docker"
```

---

## Task 2: Create knowledge_base markdown files

**Files:**
- Create: `knowledge_base/cta_copywriting.md`
- Create: `knowledge_base/value_proposition_frameworks.md`
- Create: `knowledge_base/seo_onpage_checklist.md`
- Create: `knowledge_base/core_web_vitals.md`
- Create: `knowledge_base/trust_signals.md`
- Create: `knowledge_base/cro_research.md`

- [ ] **Step 1: Create `knowledge_base/cta_copywriting.md`**

```markdown
---
title: CTA Copywriting Best Practices
category: conversion
source: internal
---

# CTA Copywriting Best Practices

Call-to-action copy is one of the highest-leverage conversion elements. The language, placement, and specificity of a CTA determines whether a visitor takes the next step or leaves.

## Principles

**Use outcome-oriented language.** The button text should describe what the user *gets*, not what they *do*. "Get My Free Audit" outperforms "Submit" because it answers the implicit question: "What happens when I click?"

**Place the primary CTA above the fold.** Users spend 80% of their time above the fold (Nielsen Norman Group). A CTA that requires scrolling to discover will be missed by most visitors.

**Use first-person phrasing.** "Start My Free Trial" consistently outperforms "Start Your Free Trial" in A/B tests, with lifts ranging from 10–90% (Unbounce, 2023).

**One primary CTA per page.** Multiple competing CTAs create decision paralysis. If secondary CTAs are necessary, make them visually subordinate (outline button vs. filled button).

**Avoid vague verbs.** "Learn More", "Click Here", "Go", "Submit" provide no information about the outcome. Replace with specific verbs: "Download", "Book", "Reserve", "Calculate", "See Results".

**Create urgency honestly.** Real scarcity works; manufactured urgency destroys trust.

## Common Issues

- Button says "Submit" or "Go" with no benefit context
- Primary CTA is below the fold on mobile
- Competing CTAs with equal visual weight
- No CTA present in the hero section

## Scoring Signal

High-scoring CTA: specific outcome language, first-person phrasing, above the fold, single primary action per section. Low-scoring CTA: generic verb only, buried below content, or absent from the page.
```

- [ ] **Step 2: Create `knowledge_base/value_proposition_frameworks.md`**

```markdown
---
title: Value Proposition Frameworks
category: conversion
source: internal
---

# Value Proposition Frameworks

A value proposition answers three questions in one sentence: who is this for, what does it do, and why should I care. Pages that communicate this clearly in the hero section convert significantly better than those that lead with brand name or tagline.

## PAS Framework (Problem–Agitate–Solution)

1. **Problem:** Name the specific pain the visitor has
2. **Agitate:** Amplify why that pain matters and what happens if it stays unsolved
3. **Solution:** Present your product/service as the relief

Best suited for landing pages targeting a known, felt pain point.

## AIDA Framework (Attention–Interest–Desire–Action)

1. **Attention:** A headline that hooks (a surprising stat, a bold claim, a question)
2. **Interest:** Explain relevance to the visitor's situation
3. **Desire:** Show the transformation or outcome (before/after, testimonial, demo)
4. **Action:** A single clear CTA

Best suited for longer-form sales pages with cold traffic.

## One-Sentence Value Proposition Test

The headline and sub-headline together must answer: "We help [who] achieve [outcome] by [mechanism]." If a visitor cannot extract this within 5 seconds, the value proposition needs work.

Weak: "Welcome to Acme Corp. Innovative Solutions for Modern Businesses."
Strong: "Audit your website in 60 seconds. Get a prioritised fix list, not a 40-page PDF."

## Common Issues

- Headline is the company name or tagline with no customer benefit
- Hero copy talks about the company ("we believe…") instead of the customer's outcome
- Benefit is vague ("save time", "grow your business") with no specificity
- Inconsistent messaging across pages

## Scoring Signal

High score: hero answers who/what/why, outcome is specific, consistent across pages. Low score: company-centric copy, vague benefit language, or no clear value proposition in the hero.
```

- [ ] **Step 3: Create `knowledge_base/seo_onpage_checklist.md`**

```markdown
---
title: SEO On-Page Checklist
category: seo
source: internal
---

# SEO On-Page Checklist

On-page SEO factors signal to search engines what a page is about and whether it deserves to rank. These are fully within the site owner's control and have direct, measurable impact on rankings.

## Title Tags

- Length: 50–60 characters (Google truncates beyond 60)
- Include the primary keyword near the start
- Be descriptive and click-worthy — the title tag is the organic search headline
- Unique per page — duplicate titles confuse crawlers and dilute rankings

## Meta Descriptions

- Length: 150–160 characters (truncated beyond this in SERPs)
- Should summarise the page and include a soft CTA ("Learn how…", "Find out…")
- Not a direct ranking factor, but affects click-through rate
- Unique per page

## Heading Structure

- Exactly one H1 per page — the primary topic of the page
- H1 should contain or be close to the primary keyword
- H2s for major sections, H3s for subsections — logical hierarchy matters
- Avoid keyword stuffing in headings

## Image Alt Text

- Every content image needs descriptive alt text (required for WCAG accessibility too)
- Alt text describes what the image shows, including relevant keywords naturally
- Decorative images use `alt=""`

## Internal Linking

- Pages should link to other relevant pages on the same site
- Anchor text should be descriptive (not "click here")
- Crawlers follow internal links to discover and index content

## Technical Basics

- Canonical tag on every page to prevent duplicate content indexing
- HTTPS enforced (HTTP pages rank lower and trigger browser security warnings)
- Mobile-responsive layout (Google uses mobile-first indexing)

## Scoring Signal

High score: unique title (50–60 chars), meta description (150–160 chars), single H1, all images have alt text, canonical present. Low score: missing or duplicate titles, no meta description, multiple or missing H1s, images without alt text.
```

- [ ] **Step 4: Create `knowledge_base/core_web_vitals.md`**

```markdown
---
title: Core Web Vitals Guidance
category: tech
source: internal
---

# Core Web Vitals Guidance

Core Web Vitals are Google's user-experience metrics that directly affect search rankings (since 2021). They measure loading performance, interactivity, and visual stability.

## LCP — Largest Contentful Paint

**Target:** ≤ 2.5 seconds
**What it measures:** Time until the largest visible element (hero image, heading) is rendered.

Common causes of poor LCP:
- Unoptimised hero images (use WebP, compress, lazy-load below-the-fold only)
- No CDN — slow origin server response
- Render-blocking JavaScript or CSS in `<head>`

## INP — Interaction to Next Paint

**Target:** ≤ 200ms (replaced FID in March 2024)
**What it measures:** Time from user input to the browser's next visual response.

Common causes of poor INP:
- Heavy JavaScript executing on the main thread
- Long tasks (>50ms) blocking input processing
- Third-party scripts (chat widgets, analytics) not loaded asynchronously

## CLS — Cumulative Layout Shift

**Target:** ≤ 0.1
**What it measures:** How much page content shifts unexpectedly during load.

Common causes of poor CLS:
- Images without explicit `width` and `height` attributes
- Ads or iframes without reserved space
- Fonts causing flash of unstyled text — use `font-display: swap`

## HTTPS

HTTPS is a confirmed ranking signal. Pages on HTTP are flagged "Not Secure" by browsers, reduce visitor trust, and rank lower. All internal links should enforce HTTPS.

## Mobile Viewport

The `<meta name="viewport" content="width=device-width, initial-scale=1">` tag is required for responsive rendering. Without it, Google's mobile-first indexer cannot properly evaluate the page.

## Scoring Signal

High score: LCP < 2.5s, no render-blocking resources, HTTPS enforced, viewport meta present, images have explicit dimensions. Low score: LCP > 4s, render-blocking scripts in head, HTTP only, no viewport meta.
```

- [ ] **Step 5: Create `knowledge_base/trust_signals.md`**

```markdown
---
title: Trust Signal Best Practices
category: trust
source: internal
---

# Trust Signal Best Practices

Trust signals reduce purchase anxiety and are essential for converting visitors who are evaluating you against alternatives. Trust is built through specificity, transparency, and social proof from credible sources.

## Testimonials and Social Proof

**Use named, attributed testimonials.** "Great service!" from "John D." is almost worthless. "Reduced our ad spend by 34% in 8 weeks" from "Maria Chen, Head of Growth at Finova" is powerful.

**Include photos.** Testimonials with photos of real people are trusted 2.5× more than text-only quotes (Brightlocal, 2022).

**Logos of recognisable clients.** A row of customer logos above the fold signals credibility before a visitor reads anything.

**Review counts and star ratings.** Link to third-party review platforms (Google, Trustpilot, G2) to make claims verifiable.

## About / Team Page

A visible About or Team page signals that real people are behind the business. Faceless companies convert worse, particularly for B2B and high-consideration purchases. Include team photos, names, and a founding story.

## Contact Information

Visible contact information (phone, email, physical address where applicable) dramatically increases trust. Its absence raises a red flag for first-time visitors. Contact info should appear in the header or footer on every page.

## Legal Pages

Privacy Policy and Terms of Service pages are mandatory for trust and legal compliance. Their presence (linked in the footer) signals that the business is accountable. GDPR and CCPA notices are expected for any business with EU or California customers.

## Trust Badges and Certifications

Industry certifications, security badges (SSL, SOC 2), money-back guarantees, and accreditations should appear near conversion points. Place trust badges where anxiety peaks — near the CTA and the price.

## Scoring Signal

High score: named photo testimonials, client logos, team page, visible contact info, privacy policy linked, trust badges near CTAs. Low score: no testimonials, no About page, contact info absent, no privacy policy.
```

- [ ] **Step 6: Create `knowledge_base/cro_research.md`**

```markdown
---
title: Conversion Rate Optimisation Research
category: conversion
source: internal
---

# Conversion Rate Optimisation Research

CRO is the systematic process of increasing the percentage of visitors who take a desired action. The findings below are grounded in industry research and A/B testing meta-analyses.

## Page Load Time and Conversion

A 1-second delay in page load time reduces conversions by 7% (Akamai). Pages that load in ≤ 2 seconds convert at 2× the rate of pages that take 5+ seconds. Mobile users are more sensitive to load time than desktop users.

## Social Proof Effects

Adding testimonials to a landing page increases conversions by 34% on average (Econsultancy). The effect is strongest when testimonials are specific and outcome-focused (metrics, before/after) and the reviewer's role and company are visible.

## Form Field Reduction

Reducing a form from 11 fields to 4 increases completions by 120% (Unbounce). Each additional field beyond 3 reduces completion probability by approximately 11%. For lead-gen, ask only for name and email on first contact.

## Pricing Transparency

Hiding pricing reduces lead quality and increases time-to-close. Visitors who see pricing before contacting are 2× more likely to convert (PriceIntelligently). If exact pricing cannot be shown, a "starting from" anchor maintains transparency.

## Above-the-Fold Optimisation

The average visitor decides whether to stay within 15 seconds. The hero section must communicate: what it is, who it's for, and what to do next — without scrolling. Pages that answer these three questions above the fold have 30–40% lower bounce rates.

## Mobile Conversion Gap

Mobile traffic typically converts at 30–50% of the desktop rate on poorly optimised sites. The gap closes when forms are minimal, CTAs are thumb-friendly (≥ 44px tap target), and load time is under 3 seconds.

## Scoring Signal

High score: fast load time, social proof visible, short form (≤ 4 fields), transparent pricing, strong above-the-fold value proposition optimised for mobile. Low score: slow load, no social proof, long forms, hidden pricing, poor mobile experience.
```

- [ ] **Step 7: Commit**

```bash
git add knowledge_base/
git commit -m "feat: add knowledge_base markdown files (6 docs)"
```

---

## Task 3: Create audits/rag/ package

**Files:**
- Create: `backend/audits/rag/__init__.py`
- Create: `backend/audits/rag/openai_client.py`
- Create: `backend/audits/rag/retrieval.py`

- [ ] **Step 1: Create `backend/audits/rag/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Create `backend/audits/rag/openai_client.py`**

```python
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    pass


def embed_text(text: str) -> list[float]:
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    try:
        response = client.embeddings.create(
            model='text-embedding-3-small',
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"OpenAI embedding failed: {e}")
        raise EmbeddingError(str(e)) from e
```

- [ ] **Step 3: Create `backend/audits/rag/retrieval.py`**

```python
import logging

from pgvector.django import CosineDistance

from audits.models import KnowledgeDoc
from .openai_client import embed_text

logger = logging.getLogger(__name__)


def retrieve_similar_docs(issue_description: str, top_k: int = 3) -> list[KnowledgeDoc]:
    query_vector = embed_text(issue_description)
    return list(
        KnowledgeDoc.objects
        .exclude(embedding=None)
        .annotate(distance=CosineDistance('embedding', query_vector))
        .order_by('distance')[:top_k]
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/audits/rag/
git commit -m "feat: add audits/rag package with openai_client and retrieval"
```

---

## Task 4: Create seed_knowledge management command

**Files:**
- Create: `backend/audits/management/__init__.py`
- Create: `backend/audits/management/commands/__init__.py`
- Create: `backend/audits/management/commands/seed_knowledge.py`

- [ ] **Step 1: Create `backend/audits/management/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Create `backend/audits/management/commands/__init__.py`** (empty file)

```python
```

- [ ] **Step 3: Create `backend/audits/management/commands/seed_knowledge.py`**

```python
import logging
from pathlib import Path

import frontmatter
from django.conf import settings
from django.core.management.base import BaseCommand

from audits.models import KnowledgeDoc
from audits.rag.openai_client import EmbeddingError, embed_text

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(settings.BASE_DIR).parent / 'knowledge_base'


def seed_knowledge_base() -> tuple[int, int]:
    """
    Scan KNOWLEDGE_BASE_DIR for *.md files, embed each, and save to KnowledgeDoc.
    Idempotent: skips docs whose title already exists in the DB.
    Returns (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob('*.md')):
        post = frontmatter.load(md_file)
        title = post.metadata.get('title', md_file.stem)
        category = post.metadata.get('category', 'general')
        source = post.metadata.get('source', md_file.name)
        content = post.content.strip()

        if KnowledgeDoc.objects.filter(title=title).exists():
            skipped += 1
            continue

        try:
            embedding = embed_text(content)
        except EmbeddingError as e:
            logger.error(f"Skipping '{title}' — embedding failed: {e}")
            continue

        KnowledgeDoc.objects.create(
            title=title,
            category=category,
            content=content,
            embedding=embedding,
            source=source,
        )
        created += 1

    return created, skipped


class Command(BaseCommand):
    help = 'Seed the KnowledgeDoc table from knowledge_base/*.md files'

    def handle(self, *args, **options):
        created, skipped = seed_knowledge_base()
        self.stdout.write(f"Done: {created} created, {skipped} skipped")
```

- [ ] **Step 4: Commit**

```bash
git add backend/audits/management/
git commit -m "feat: add seed_knowledge management command"
```

---

## Task 5: Add seed API endpoint

**Files:**
- Modify: `backend/audits/views.py`
- Modify: `backend/audits/urls.py`

- [ ] **Step 1: Add `SeedKnowledgeView` to `backend/audits/views.py`**

Add the following import at the top of the existing imports block:

```python
from .management.commands.seed_knowledge import seed_knowledge_base
```

Add the following class at the end of the file:

```python
class SeedKnowledgeView(APIView):
    def post(self, request):
        try:
            created, skipped = seed_knowledge_base()
            return Response({'created': created, 'skipped': skipped})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

- [ ] **Step 2: Register the route in `backend/audits/urls.py`**

Add to the existing `urlpatterns` list:

```python
path('knowledge/seed/', views.SeedKnowledgeView.as_view(), name='knowledge-seed'),
```

Full `urlpatterns` after edit:

```python
urlpatterns = [
    path('businesses/', views.BusinessListCreateView.as_view(), name='business-list'),
    path('businesses/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('businesses/<int:pk>/audit/', views.AuditTriggerView.as_view(), name='audit-trigger'),
    path('audits/<int:pk>/status/', views.AuditStatusView.as_view(), name='audit-status'),
    path('audits/<int:pk>/', views.AuditReportDetailView.as_view(), name='audit-report'),
    path('audits/<int:pk>/issues/', views.AuditIssueListView.as_view(), name='audit-issues'),
    path('knowledge/seed/', views.SeedKnowledgeView.as_view(), name='knowledge-seed'),
]
```

- [ ] **Step 3: Commit**

```bash
git add backend/audits/views.py backend/audits/urls.py
git commit -m "feat: add POST /api/knowledge/seed/ endpoint"
```

---

## Task 6: Write tests

**Files:**
- Create: `backend/audits/tests/test_rag.py`

- [ ] **Step 1: Create `backend/audits/tests/test_rag.py`**

```python
from unittest.mock import patch

from django.test import TestCase

from audits.management.commands.seed_knowledge import seed_knowledge_base
from audits.models import KnowledgeDoc
from audits.rag.retrieval import retrieve_similar_docs


def _make_vector(hot_index: int) -> list[float]:
    v = [0.0] * 1536
    v[hot_index] = 1.0
    return v


class RetrievalTest(TestCase):
    def setUp(self):
        # 3 docs aligned to dimension 0 (close to query)
        for i in range(3):
            KnowledgeDoc.objects.create(
                title=f"Close Doc {i}",
                category="conversion",
                content="CTA best practices",
                embedding=_make_vector(0),
                source="test",
            )
        # 2 docs aligned to dimension 1 (far from query)
        for i in range(2):
            KnowledgeDoc.objects.create(
                title=f"Far Doc {i}",
                category="seo",
                content="SEO checklist",
                embedding=_make_vector(1),
                source="test",
            )

    def test_retrieve_returns_top_3(self):
        with patch('audits.rag.retrieval.embed_text', return_value=_make_vector(0)):
            results = retrieve_similar_docs("weak CTA with no benefit language")

        self.assertEqual(len(results), 3)
        for doc in results:
            self.assertIn("Close Doc", doc.title)

    def test_retrieve_skips_null_embeddings(self):
        KnowledgeDoc.objects.create(
            title="No Embedding Doc",
            category="trust",
            content="trust signals",
            embedding=None,
            source="test",
        )
        with patch('audits.rag.retrieval.embed_text', return_value=_make_vector(0)):
            results = retrieve_similar_docs("missing trust signals")

        titles = [r.title for r in results]
        self.assertNotIn("No Embedding Doc", titles)

    def test_seed_is_idempotent(self):
        with patch('audits.management.commands.seed_knowledge.embed_text', return_value=_make_vector(0)):
            seed_knowledge_base()
            count_after_first = KnowledgeDoc.objects.count()
            seed_knowledge_base()
            count_after_second = KnowledgeDoc.objects.count()

        self.assertEqual(count_after_first, count_after_second)
```

- [ ] **Step 2: Commit**

```bash
git add backend/audits/tests/test_rag.py
git commit -m "test: add RAG retrieval and seed idempotency tests"
```

---

## Task 7: Run full test suite

- [ ] **Step 1: Rebuild the Docker image to pick up new dependencies**

```bash
docker compose build backend celery
```

Expected: build completes without error. `openai` and `python-frontmatter` appear in pip install output.

- [ ] **Step 2: Run the full test suite**

```bash
docker compose run --rm backend python manage.py test audits --verbosity=2
```

Expected output includes:
```
test_retrieve_returns_top_3 (audits.tests.test_rag.RetrievalTest) ... ok
test_retrieve_skips_null_embeddings (audits.tests.test_rag.RetrievalTest) ... ok
test_seed_is_idempotent (audits.tests.test_rag.RetrievalTest) ... ok
...
Ran N tests in X.XXXs
OK
```

If any test fails, fix it before proceeding.

---

## Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Mark Phase 4 complete in CLAUDE.md**

In the Phase Completion Status section, change:
```
- [ ] Phase 4 — RAG Knowledge System
```
to:
```
- [x] Phase 4 — RAG Knowledge System
```

- [ ] **Step 2: Update Folder Structure section** to include the new directories:

```
ai-business-audit/
├── CLAUDE.md
├── REQUIREMENTS.md
├── .env.example
├── docker-compose.yml
├── knowledge_base/        # Markdown best-practice docs for RAG seeding
├── backend/
│   ├── config/
│   ├── core/
│   └── audits/
│       ├── scorers/
│       ├── rag/           # openai_client.py, retrieval.py
│       ├── management/
│       │   └── commands/
│       │       └── seed_knowledge.py
│       ├── scraper.py
│       ├── tasks.py
│       ├── serializers.py
│       └── views.py
└── frontend/
```

- [ ] **Step 3: Add to Key Architectural Decisions section:**

```
- **audits/rag/ sub-package** — mirrors scorers/ pattern; openai_client.py wraps the OpenAI SDK for embeddings, retrieval.py runs cosine similarity via pgvector CosineDistance annotation
- **Seed endpoint is synchronous** — seeding ~6 docs takes <5s; async overhead is not justified for a one-time admin operation
- **YAML frontmatter in markdown** — each knowledge_base/*.md file carries title/category/source metadata; parsed with python-frontmatter
- **Idempotent seeding** — seed_knowledge_base() skips any KnowledgeDoc whose title already exists; safe to run multiple times
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — Phase 4 complete"
```
