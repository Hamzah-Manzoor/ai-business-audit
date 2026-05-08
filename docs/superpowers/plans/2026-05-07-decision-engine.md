# Decision Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a decision engine that takes `AuditIssue` records + RAG context and produces a prioritized `Recommendation` list exposed via `GET /api/audits/<id>/recommendations/`.

**Architecture:** A new `audits/decision/` sub-package (mirrors `audits/scorers/` and `audits/rag/`) holds the rules engine and LLM client. A new `generate_recommendations` Celery task is triggered by `.delay()` at the end of `run_audit`'s success path. The API layer adds a serializer, list view, and URL route.

**Tech Stack:** Django 4.2, DRF, Celery 5.3, Anthropic Claude API (`claude-sonnet-4-6`), Pydantic, pgvector (existing), fastembed (existing RAG embeddings)

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `audits/decision/__init__.py` | Package marker |
| Create | `audits/decision/schemas.py` | `RecommendationResult` Pydantic model |
| Create | `audits/decision/rules.py` | `apply_priority_rules()` — deterministic tier sorter |
| Create | `audits/decision/claude_client.py` | `generate_recommendations_with_claude()` — LLM call |
| Modify | `audits/tasks.py` | Add `generate_recommendations` task + `.delay()` call in `run_audit` |
| Modify | `audits/serializers.py` | Add `RecommendationSerializer` |
| Modify | `audits/views.py` | Add `RecommendationListView` |
| Modify | `audits/urls.py` | Add `audits/<pk>/recommendations/` route |
| Modify | `audits/tests/test_run_audit.py` | Mock `generate_recommendations` in existing tests; add chain test |
| Create | `audits/tests/test_decision_rules.py` | Unit tests for `apply_priority_rules` |
| Create | `audits/tests/test_decision_claude_client.py` | Unit tests for `generate_recommendations_with_claude` |
| Create | `audits/tests/test_generate_recommendations_task.py` | Integration tests for the Celery task |
| Modify | `CLAUDE.md` | Mark Phase 5 complete, update folder structure |

---

## Task 1: Create `audits/decision/` package with `schemas.py`

**Files:**
- Create: `audits/decision/__init__.py`
- Create: `audits/decision/schemas.py`

- [ ] **Step 1: Create the package directory and empty `__init__.py`**

```bash
mkdir -p backend/audits/decision
touch backend/audits/decision/__init__.py
```

- [ ] **Step 2: Write `schemas.py`**

Create `backend/audits/decision/schemas.py`:

```python
from typing import Literal
from pydantic import BaseModel


class RecommendationResult(BaseModel):
    issue_id: int
    title: str
    effort: Literal['low', 'medium', 'high']
    impact: Literal['low', 'medium', 'high']
    priority_score: float
    rationale: str
```

- [ ] **Step 3: Verify the schema imports and validates correctly**

Run inside Docker:

```bash
docker compose exec backend python -c "
from audits.decision.schemas import RecommendationResult
r = RecommendationResult(issue_id=1, title='Fix HTTPS', effort='low', impact='high', priority_score=9.5, rationale='Critical for trust.')
print(r)
"
```

Expected output (no errors):
```
issue_id=1 title='Fix HTTPS' effort='low' impact='high' priority_score=9.5 rationale='Critical for trust.'
```

- [ ] **Step 4: Commit**

```bash
git add backend/audits/decision/
git commit -m "feat: add audits/decision package with RecommendationResult schema"
```

---

## Task 2: Implement `rules.py` (TDD)

**Files:**
- Create: `audits/decision/rules.py`
- Create: `audits/tests/test_decision_rules.py`

- [ ] **Step 1: Write failing tests**

Create `backend/audits/tests/test_decision_rules.py`:

```python
from unittest.mock import MagicMock
from django.test import TestCase
from audits.decision.rules import apply_priority_rules


def _issue(id, severity, parameter_key, score, category='seo'):
    issue = MagicMock()
    issue.id = id
    issue.severity = severity
    issue.parameter_key = parameter_key
    issue.score = score
    issue.category = category
    return issue


def _report(seo=80, conversion=80, content=80, tech=80, trust=80):
    report = MagicMock()
    report.seo_score = seo
    report.conversion_score = conversion
    report.content_score = content
    report.tech_score = tech
    report.trust_score = trust
    return report


class ApplyPriorityRulesTest(TestCase):
    def test_critical_severity_is_blocker(self):
        issue = _issue(1, 'critical', 'meta_title', 3)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_https_parameter_key_is_blocker(self):
        issue = _issue(1, 'warning', 'https', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_broken_links_parameter_key_is_blocker(self):
        issue = _issue(1, 'warning', 'broken_links', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'blocker')

    def test_category_score_below_40_is_blocker(self):
        issue = _issue(1, 'warning', 'cta_clarity', 5, category='conversion')
        result = apply_priority_rules([issue], _report(conversion=35))
        self.assertEqual(result[0][1], 'blocker')

    def test_category_score_exactly_40_is_not_blocker(self):
        issue = _issue(1, 'warning', 'cta_clarity', 5, category='conversion')
        result = apply_priority_rules([issue], _report(conversion=40))
        self.assertEqual(result[0][1], 'warning')

    def test_warning_severity_is_warning_tier(self):
        issue = _issue(1, 'warning', 'meta_description', 5)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'warning')

    def test_info_severity_is_info_tier(self):
        issue = _issue(1, 'info', 'canonical', 7)
        result = apply_priority_rules([issue], _report())
        self.assertEqual(result[0][1], 'info')

    def test_blocker_before_warning_before_info(self):
        blocker = _issue(1, 'critical', 'https', 2, 'tech')
        warning = _issue(2, 'warning', 'meta_title', 5, 'seo')
        info = _issue(3, 'info', 'canonical', 7, 'seo')
        result = apply_priority_rules([info, warning, blocker], _report())
        self.assertEqual([t for _, t in result], ['blocker', 'warning', 'info'])

    def test_within_tier_sorted_by_score_ascending(self):
        high_score = _issue(1, 'warning', 'meta_title', 6)
        low_score = _issue(2, 'warning', 'meta_description', 4)
        result = apply_priority_rules([high_score, low_score], _report())
        self.assertEqual(result[0][0].id, 2)
        self.assertEqual(result[1][0].id, 1)

    def test_returns_list_of_tuples(self):
        issue = _issue(1, 'warning', 'meta_title', 5)
        result = apply_priority_rules([issue], _report())
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], tuple)
        self.assertEqual(len(result[0]), 2)

    def test_empty_issues_returns_empty_list(self):
        result = apply_priority_rules([], _report())
        self.assertEqual(result, [])
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_decision_rules -v 2
```

Expected: `ImportError: cannot import name 'apply_priority_rules' from 'audits.decision.rules'`

- [ ] **Step 3: Implement `rules.py`**

Create `backend/audits/decision/rules.py`:

```python
_BLOCKER_KEYS = {'https', 'broken_links'}

_CATEGORY_SCORE_ATTR = {
    'seo': 'seo_score',
    'conversion': 'conversion_score',
    'content': 'content_score',
    'tech': 'tech_score',
    'trust': 'trust_score',
}

_TIER_ORDER = {'blocker': 0, 'warning': 1, 'info': 2}


def apply_priority_rules(issues, report):
    """
    Returns list of (AuditIssue, tier_label) tuples sorted by priority.
    Tier order: blocker → warning → info. Within each tier: score ascending (worst first).
    """
    def _tier(issue):
        score_attr = _CATEGORY_SCORE_ATTR.get(issue.category)
        category_score = getattr(report, score_attr, 100) if score_attr else 100
        if (
            issue.severity == 'critical'
            or issue.parameter_key in _BLOCKER_KEYS
            or category_score < 40
        ):
            return 'blocker'
        if issue.severity == 'warning':
            return 'warning'
        return 'info'

    tagged = [(issue, _tier(issue)) for issue in issues]
    tagged.sort(key=lambda x: (_TIER_ORDER[x[1]], x[0].score))
    return tagged
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_decision_rules -v 2
```

Expected: `OK` — all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/audits/decision/rules.py backend/audits/tests/test_decision_rules.py
git commit -m "feat: add decision rules engine with priority tier sorting"
```

---

## Task 3: Implement `claude_client.py` (TDD)

**Files:**
- Create: `audits/decision/claude_client.py`
- Create: `audits/tests/test_decision_claude_client.py`

- [ ] **Step 1: Write failing tests**

Create `backend/audits/tests/test_decision_claude_client.py`:

```python
from unittest.mock import MagicMock, patch
from django.test import TestCase
from audits.decision.claude_client import generate_recommendations_with_claude
from audits.decision.schemas import RecommendationResult

_SAMPLE_ISSUES = [
    {
        'issue_id': 1,
        'tier': 'blocker',
        'category': 'tech',
        'severity': 'critical',
        'title': 'HTTPS not enforced',
        'description': 'Site is served over HTTP.',
        'parameter_key': 'https',
        'score': 0,
        'rag_context': [
            {'title': 'HTTPS Best Practices', 'content': 'Always serve over HTTPS.'}
        ],
    }
]

_TOOL_RESPONSE = {
    'recommendations': [
        {
            'issue_id': 1,
            'title': 'Enable HTTPS across all pages',
            'effort': 'low',
            'impact': 'high',
            'priority_score': 9.5,
            'rationale': 'HTTPS is required for trust and SEO ranking.',
        }
    ]
}


def _make_mock_response(tool_input):
    tool_block = MagicMock()
    tool_block.type = 'tool_use'
    tool_block.input = tool_input
    response = MagicMock()
    response.content = [tool_block]
    response.usage.input_tokens = 200
    response.usage.output_tokens = 80
    return response


class GenerateRecommendationsWithClaudeTest(TestCase):
    def test_returns_list_of_recommendation_results(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(_TOOL_RESPONSE)
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], RecommendationResult)

    def test_result_fields_are_correct(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = _make_mock_response(_TOOL_RESPONSE)
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        r = results[0]
        self.assertEqual(r.issue_id, 1)
        self.assertEqual(r.title, 'Enable HTTPS across all pages')
        self.assertEqual(r.effort, 'low')
        self.assertEqual(r.impact, 'high')
        self.assertAlmostEqual(r.priority_score, 9.5)

    def test_retries_on_failure_then_succeeds(self):
        ok = _make_mock_response(_TOOL_RESPONSE)
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.side_effect = [Exception('timeout'), ok]
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(len(results), 1)

    def test_returns_empty_list_after_three_failures(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception('api error')
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(results, [])

    def test_raises_on_missing_tool_block(self):
        response = MagicMock()
        response.content = []
        response.usage.input_tokens = 50
        response.usage.output_tokens = 10
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            MockClient.return_value.messages.create.return_value = response
            results = generate_recommendations_with_claude(_SAMPLE_ISSUES)
        self.assertEqual(results, [])

    def test_uses_correct_model_and_tool(self):
        with patch('audits.decision.claude_client.anthropic.Anthropic') as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _make_mock_response(_TOOL_RESPONSE)
            generate_recommendations_with_claude(_SAMPLE_ISSUES)
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'claude-sonnet-4-6')
        self.assertEqual(call_kwargs['tool_choice'], {'type': 'tool', 'name': 'submit_recommendations'})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_decision_claude_client -v 2
```

Expected: `ImportError: cannot import name 'generate_recommendations_with_claude'`

- [ ] **Step 3: Implement `claude_client.py`**

Create `backend/audits/decision/claude_client.py`:

```python
import json
import logging
import time

import anthropic

from .schemas import RecommendationResult

logger = logging.getLogger(__name__)

_COST_PER_INPUT_TOKEN = 3.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000

_TOOL_DEFINITION = {
    'name': 'submit_recommendations',
    'description': 'Submit the prioritized recommendation list.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'recommendations': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'issue_id':       {'type': 'integer'},
                        'title':          {'type': 'string'},
                        'effort':         {'type': 'string', 'enum': ['low', 'medium', 'high']},
                        'impact':         {'type': 'string', 'enum': ['low', 'medium', 'high']},
                        'priority_score': {'type': 'number', 'minimum': 0, 'maximum': 10},
                        'rationale':      {'type': 'string'},
                    },
                    'required': ['issue_id', 'title', 'effort', 'impact', 'priority_score', 'rationale'],
                },
            },
        },
        'required': ['recommendations'],
    },
}


def _build_prompt(ranked_issues_with_context: list[dict]) -> str:
    lines = [
        'You are an expert business website consultant.',
        '',
        'Below is a prioritized list of issues found during a website audit,',
        'along with relevant best-practice context for each issue.',
        '',
        'For each issue, produce one recommendation with:',
        '- A clear action title',
        '- Effort estimate (low/medium/high)',
        '- Impact estimate (low/medium/high)',
        '- Priority score (0-10, higher = more urgent)',
        '- A one-sentence rationale that cites the provided context',
        '',
        'Issues:',
    ]
    for item in ranked_issues_with_context:
        lines.append(
            f"\n[{item['tier'].upper()}] {item['title']} "
            f"({item['category']}, score: {item['score']}/10, id: {item['issue_id']})"
        )
        lines.append(f"Description: {item['description']}")
        lines.append('Best-practice context:')
        for doc in item['rag_context']:
            lines.append(f"  - {doc['title']}: {doc['content']}")
    return '\n'.join(lines)


def generate_recommendations_with_claude(
    ranked_issues_with_context: list[dict],
    prompt_version: str = 'v1',
) -> list[RecommendationResult]:
    client = anthropic.Anthropic()
    prompt = _build_prompt(ranked_issues_with_context)

    for attempt in range(1, 4):
        t_start = time.monotonic()
        input_tokens = 0
        output_tokens = 0
        try:
            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=2048,
                tools=[_TOOL_DEFINITION],
                tool_choice={'type': 'tool', 'name': 'submit_recommendations'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            latency_ms = int((time.monotonic() - t_start) * 1000)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            tool_block = next((b for b in response.content if b.type == 'tool_use'), None)
            if tool_block is None:
                raise ValueError('No tool_use block in response')

            results = [RecommendationResult(**r) for r in tool_block.input['recommendations']]
            _log(input_tokens, output_tokens, latency_ms, prompt_version, attempt, True)
            return results

        except Exception as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            _log(input_tokens, output_tokens, latency_ms, prompt_version, attempt, False, str(exc))
            logger.warning(f'Recommendation LLM attempt {attempt}/3 failed: {exc}')

    logger.error('All 3 recommendation LLM attempts failed, returning empty list')
    return []


def _log(input_tokens, output_tokens, latency_ms, prompt_version, attempt, success, error=None):
    cost_usd = (input_tokens * _COST_PER_INPUT_TOKEN) + (output_tokens * _COST_PER_OUTPUT_TOKEN)
    record = {
        'event': 'llm_call',
        'category': 'recommendations',
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

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_decision_claude_client -v 2
```

Expected: `OK` — all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/audits/decision/claude_client.py backend/audits/tests/test_decision_claude_client.py
git commit -m "feat: add decision engine LLM client with retry and structured tool call"
```

---

## Task 4: Implement `generate_recommendations` Celery task (TDD)

**Files:**
- Modify: `audits/tasks.py`
- Create: `audits/tests/test_generate_recommendations_task.py`

- [ ] **Step 1: Write failing tests**

Create `backend/audits/tests/test_generate_recommendations_task.py`:

```python
from unittest.mock import patch
from django.test import TestCase
from audits.models import AuditJob, AuditReport, AuditIssue, Recommendation, Business
from audits.decision.schemas import RecommendationResult


def _make_recommendation_result(issue_id):
    return RecommendationResult(
        issue_id=issue_id,
        title='Fix the issue',
        effort='low',
        impact='medium',
        priority_score=6.0,
        rationale='Grounded in best-practice context.',
    )


class GenerateRecommendationsTaskTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Test Co', url='https://example.com')
        self.job = AuditJob.objects.create(business=self.business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=65,
            seo_score=55,
            conversion_score=70,
            content_score=65,
            tech_score=80,
            trust_score=50,
        )
        self.issue = AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Missing meta description',
            description='No meta description found on the homepage.',
            parameter_key='meta_description',
            score=5,
        )

    def test_creates_recommendation_records(self):
        mock_rec = _make_recommendation_result(self.issue.id)
        with patch('audits.tasks.retrieve_similar_docs', return_value=[]):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[mock_rec]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 1)
        rec = Recommendation.objects.get(report=self.report)
        self.assertEqual(rec.title, 'Fix the issue')
        self.assertEqual(rec.effort, 'low')
        self.assertEqual(rec.impact, 'medium')
        self.assertAlmostEqual(rec.priority_score, 6.0)
        self.assertEqual(rec.issue, self.issue)

    def test_does_not_change_job_status_on_llm_failure(self):
        with patch('audits.tasks.retrieve_similar_docs', return_value=[]):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'complete')

    def test_handles_missing_report_gracefully(self):
        business2 = Business.objects.create(name='Other Co', url='https://other.com')
        job2 = AuditJob.objects.create(business=business2, status='complete')
        # No AuditReport for job2 — task should not raise
        from audits.tasks import generate_recommendations
        generate_recommendations(job2.id)
        job2.refresh_from_db()
        self.assertEqual(job2.status, 'complete')

    def test_rag_retrieval_failure_does_not_crash_task(self):
        mock_rec = _make_recommendation_result(self.issue.id)
        with patch('audits.tasks.retrieve_similar_docs', side_effect=Exception('vector DB down')):
            with patch('audits.tasks.generate_recommendations_with_claude', return_value=[mock_rec]):
                from audits.tasks import generate_recommendations
                generate_recommendations(self.job.id)

        # Task survives; recommendation still created with empty rag context
        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 1)

    def test_creates_no_records_when_no_issues(self):
        AuditIssue.objects.filter(report=self.report).delete()
        from audits.tasks import generate_recommendations
        generate_recommendations(self.job.id)
        self.assertEqual(Recommendation.objects.filter(report=self.report).count(), 0)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_generate_recommendations_task -v 2
```

Expected: `ImportError` or `AttributeError` — `generate_recommendations` does not exist yet in `tasks.py`.

- [ ] **Step 3: Add imports to `tasks.py`**

Add these three lines to the top of `backend/audits/tasks.py`, after the existing scorer imports:

```python
from .decision.rules import apply_priority_rules
from .decision.claude_client import generate_recommendations_with_claude
from .rag.retrieval import retrieve_similar_docs
```

- [ ] **Step 4: Add `generate_recommendations` task to `tasks.py`**

Append to the bottom of `backend/audits/tasks.py`:

```python
@shared_task
def generate_recommendations(audit_job_id: int):
    from .models import AuditJob, AuditReport, AuditIssue, Recommendation

    try:
        job = AuditJob.objects.get(pk=audit_job_id)
        report = AuditReport.objects.get(audit_job=job)
        issues = list(AuditIssue.objects.filter(report=report))

        if not issues:
            logger.info(f'generate_recommendations: no issues for job {audit_job_id}')
            return

        ranked = apply_priority_rules(issues, report)

        ranked_issues_with_context = []
        for issue, tier in ranked:
            try:
                docs = retrieve_similar_docs(issue.description, top_k=3)
            except Exception as e:
                logger.warning(f'RAG retrieval failed for issue {issue.id}: {e}')
                docs = []
            ranked_issues_with_context.append({
                'issue_id': issue.id,
                'tier': tier,
                'category': issue.category,
                'severity': issue.severity,
                'title': issue.title,
                'description': issue.description,
                'parameter_key': issue.parameter_key,
                'score': issue.score,
                'rag_context': [
                    {'title': d.title, 'content': d.content[:300]}
                    for d in docs
                ],
            })

        results = generate_recommendations_with_claude(ranked_issues_with_context)

        issue_map = {issue.id: issue for issue, _ in ranked}
        Recommendation.objects.bulk_create([
            Recommendation(
                report=report,
                issue=issue_map.get(r.issue_id),
                priority_score=r.priority_score,
                effort=r.effort,
                impact=r.impact,
                title=r.title,
                rationale=r.rationale,
            )
            for r in results
        ])
        logger.info(
            f'generate_recommendations: created {len(results)} recommendations for job {audit_job_id}'
        )

    except Exception as exc:
        logger.error(f'generate_recommendations failed for job {audit_job_id}: {exc}')
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_generate_recommendations_task -v 2
```

Expected: `OK` — all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/audits/tasks.py backend/audits/tests/test_generate_recommendations_task.py
git commit -m "feat: add generate_recommendations Celery task"
```

---

## Task 5: Hook `generate_recommendations` into `run_audit`

**Files:**
- Modify: `audits/tasks.py` (add `.delay()` call)
- Modify: `audits/tests/test_run_audit.py` (add mock + new chain test)

- [ ] **Step 1: Update existing `RunAuditTaskTest` to mock `generate_recommendations`**

In `backend/audits/tests/test_run_audit.py`, update `RunAuditTaskTest.setUp` to add a patcher so the existing tests do not actually invoke the new task:

```python
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
        self._gen_recs_patcher = patch('audits.tasks.generate_recommendations')
        self.mock_gen_recs = self._gen_recs_patcher.start()
        self.addCleanup(self._gen_recs_patcher.stop)
```

The rest of the `RunAuditTaskTest` methods remain unchanged.

- [ ] **Step 2: Add new chain test class to `test_run_audit.py`**

Append at the bottom of `backend/audits/tests/test_run_audit.py`:

```python
class RunAuditChainsGenerateRecommendationsTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Chain Co', url='https://chain.com')
        self.job = AuditJob.objects.create(business=self.business, status='running')
        ScrapedPage.objects.create(
            business=self.business,
            audit_job=self.job,
            url='https://chain.com',
            html_content='<html></html>',
            extracted_text='content',
            meta_title='Title',
            meta_description='Desc',
            h1_tags=[],
            h2_tags=[],
            image_alts=[],
            internal_links=[],
            https=True,
            status_code=200,
            load_time_ms=500,
        )

    @patch('audits.tasks.generate_recommendations')
    @patch('audits.tasks.score_seo')
    @patch('audits.tasks.score_tech')
    @patch('audits.tasks.score_conversion')
    @patch('audits.tasks.score_content')
    @patch('audits.tasks.score_trust')
    def test_chains_generate_recommendations_on_success(
        self, mock_trust, mock_content, mock_conv, mock_tech, mock_seo, mock_gen_recs
    ):
        from audits.scorers.schemas import CategoryResult
        mock_seo.return_value = CategoryResult(category='seo', score=90, parameters=[], top_issues=[], summary='Good.')
        mock_tech.return_value = CategoryResult(category='tech', score=90, parameters=[], top_issues=[], summary='Good.')
        mock_conv.return_value = CategoryResult(category='conversion', score=90, parameters=[], top_issues=[], summary='Good.')
        mock_content.return_value = CategoryResult(category='content', score=90, parameters=[], top_issues=[], summary='Good.')
        mock_trust.return_value = CategoryResult(category='trust', score=90, parameters=[], top_issues=[], summary='Good.')

        from audits.tasks import run_audit
        run_audit(self.job.id)

        mock_gen_recs.delay.assert_called_once_with(self.job.id)
```

- [ ] **Step 3: Run existing `test_run_audit.py` to confirm they still pass (before touching `run_audit`)**

```bash
docker compose exec backend python manage.py test audits.tests.test_run_audit -v 2
```

Expected: All existing tests pass. The new `test_chains_generate_recommendations_on_success` FAILS because `generate_recommendations.delay` is not yet called.

- [ ] **Step 4: Add `.delay()` call to `run_audit` in `tasks.py`**

In `backend/audits/tasks.py`, find the success path in `run_audit` — the lines that set job status to `complete`:

```python
        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        logger.info(f"run_audit completed for job {audit_job_id}: overall_score={overall}")
```

Add one line after the `logger.info` call:

```python
        job.status = 'complete'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        logger.info(f"run_audit completed for job {audit_job_id}: overall_score={overall}")
        generate_recommendations.delay(audit_job_id)
```

- [ ] **Step 5: Run all `test_run_audit.py` tests to confirm they all pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_run_audit -v 2
```

Expected: `OK` — all tests including `test_chains_generate_recommendations_on_success` pass.

- [ ] **Step 6: Commit**

```bash
git add backend/audits/tasks.py backend/audits/tests/test_run_audit.py
git commit -m "feat: chain generate_recommendations from run_audit on success"
```

---

## Task 6: Add API layer — serializer, view, URL

**Files:**
- Modify: `audits/serializers.py`
- Modify: `audits/views.py`
- Modify: `audits/urls.py`
- Modify: `audits/tests/test_audit_views.py` (or create `audits/tests/test_recommendations_api.py`)

- [ ] **Step 1: Write failing API test**

Create `backend/audits/tests/test_recommendations_api.py`:

```python
from django.test import TestCase
from django.urls import reverse
from audits.models import AuditJob, AuditReport, AuditIssue, Recommendation, Business


class RecommendationListViewTest(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='API Co', url='https://api.com')
        self.job = AuditJob.objects.create(business=self.business, status='complete')
        self.report = AuditReport.objects.create(
            audit_job=self.job,
            overall_score=70,
            seo_score=60,
            conversion_score=75,
            content_score=70,
            tech_score=80,
            trust_score=65,
        )
        self.issue = AuditIssue.objects.create(
            report=self.report,
            category='seo',
            severity='warning',
            title='Missing meta description',
            description='No meta description found.',
            parameter_key='meta_description',
            score=5,
        )
        self.rec = Recommendation.objects.create(
            report=self.report,
            issue=self.issue,
            priority_score=7.5,
            effort='low',
            impact='high',
            title='Add a compelling meta description',
            rationale='Meta descriptions improve CTR by setting user expectations.',
        )

    def test_returns_200(self):
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_returns_recommendation_fields(self):
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(len(data), 1)
        rec = data[0]
        self.assertEqual(rec['title'], 'Add a compelling meta description')
        self.assertEqual(rec['effort'], 'low')
        self.assertEqual(rec['impact'], 'high')
        self.assertAlmostEqual(rec['priority_score'], 7.5)
        self.assertEqual(rec['issue_id'], self.issue.id)
        self.assertIn('rationale', rec)
        self.assertIn('created_at', rec)

    def test_returns_empty_list_when_no_recommendations(self):
        Recommendation.objects.filter(report=self.report).delete()
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        self.assertEqual(response.json(), [])

    def test_returns_404_for_nonexistent_job(self):
        url = reverse('audit-recommendations', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_ordered_by_priority_score_descending(self):
        Recommendation.objects.create(
            report=self.report,
            priority_score=9.0,
            effort='high',
            impact='high',
            title='High priority rec',
            rationale='Very urgent.',
        )
        url = reverse('audit-recommendations', kwargs={'pk': self.job.id})
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertGreater(data[0]['priority_score'], data[1]['priority_score'])
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec backend python manage.py test audits.tests.test_recommendations_api -v 2
```

Expected: `NoReverseMatch` — URL `audit-recommendations` not yet registered.

- [ ] **Step 3: Add `RecommendationSerializer` to `serializers.py`**

Add to the bottom of `backend/audits/serializers.py`:

```python
from .models import AuditIssue, AuditJob, AuditReport, Business, Recommendation


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ['id', 'issue_id', 'priority_score', 'effort', 'impact', 'title', 'rationale', 'created_at']
        read_only_fields = fields
```

Note: update the existing `from .models import ...` line at the top of `serializers.py` to include `Recommendation`.

- [ ] **Step 4: Add `RecommendationListView` to `views.py`**

Add to the bottom of `backend/audits/views.py`:

```python
from .serializers import (
    AuditIssueSerializer,
    AuditJobStatusSerializer,
    AuditReportSerializer,
    BusinessSerializer,
    RecommendationSerializer,
)


class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        report = get_object_or_404(AuditReport, audit_job_id=self.kwargs['pk'])
        return report.recommendations.all()
```

Note: update the existing `from .serializers import (...)` block to include `RecommendationSerializer`.

- [ ] **Step 5: Register the URL in `urls.py`**

In `backend/audits/urls.py`, add one line to `urlpatterns`:

```python
urlpatterns = [
    path('businesses/', views.BusinessListCreateView.as_view(), name='business-list'),
    path('businesses/<int:pk>/', views.BusinessDetailView.as_view(), name='business-detail'),
    path('businesses/<int:pk>/audit/', views.AuditTriggerView.as_view(), name='audit-trigger'),
    path('audits/<int:pk>/status/', views.AuditStatusView.as_view(), name='audit-status'),
    path('audits/<int:pk>/', views.AuditReportDetailView.as_view(), name='audit-report'),
    path('audits/<int:pk>/issues/', views.AuditIssueListView.as_view(), name='audit-issues'),
    path('audits/<int:pk>/recommendations/', views.RecommendationListView.as_view(), name='audit-recommendations'),
    path('knowledge/seed/', views.SeedKnowledgeView.as_view(), name='knowledge-seed'),
]
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
docker compose exec backend python manage.py test audits.tests.test_recommendations_api -v 2
```

Expected: `OK` — all 5 tests pass.

- [ ] **Step 7: Run the full test suite to confirm no regressions**

```bash
docker compose exec backend python manage.py test audits -v 2
```

Expected: All tests pass with no failures or errors.

- [ ] **Step 8: Commit**

```bash
git add backend/audits/serializers.py backend/audits/views.py backend/audits/urls.py backend/audits/tests/test_recommendations_api.py
git commit -m "feat: add RecommendationSerializer, RecommendationListView, and /api/audits/<id>/recommendations/ endpoint"
```

---

## Task 7: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Phase 5 status to complete**

In `CLAUDE.md`, find:
```markdown
- [ ] Phase 5 — Decision Engine
```
Change to:
```markdown
- [x] Phase 5 — Decision Engine
```

- [ ] **Step 2: Update the Folder Structure section**

Add the `decision/` sub-package to the audits directory listing:

```
│       ├── decision/         # Decision engine
│       │   ├── rules.py          # apply_priority_rules() — deterministic tier sorter
│       │   ├── claude_client.py  # generate_recommendations_with_claude() — LLM reasoning call
│       │   └── schemas.py        # RecommendationResult Pydantic model
```

- [ ] **Step 3: Add a Key Architectural Decision entry**

Add to the "Key Architectural Decisions" section:

```markdown
- **decision/ sub-package** — mirrors scorers/ and rag/ pattern; rules.py handles deterministic priority tiering (critical → blocker, low category score → blocker), claude_client.py makes a single LLM call with all ranked issues + per-issue RAG context; generate_recommendations Celery task chains from run_audit via .delay() — failure is logged but does not flip job status since the audit itself is already complete
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mark Phase 5 complete, update CLAUDE.md with decision engine architecture"
```
