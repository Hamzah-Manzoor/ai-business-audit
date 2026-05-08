# Phase 5 — Decision Engine Design

**Date:** 2026-05-07  
**Branch:** `feat/decision-engine`  
**Status:** Approved, ready for implementation

---

## Overview

Phase 5 takes the `AuditReport` + `AuditIssue` records produced by Phase 3 and the RAG knowledge base from Phase 4 and turns them into a prioritized `Recommendation` list. The core loop is: rules engine sorts issues by urgency → RAG retrieves relevant best-practice docs per issue → Claude produces a structured recommendation list → records saved to DB → exposed via REST API.

---

## Architecture

### New Package: `audits/decision/`

Mirrors the existing `audits/scorers/` and `audits/rag/` sub-packages. Each file has one clear responsibility.

```
audits/decision/
├── __init__.py
├── rules.py          # deterministic priority sorter
├── schemas.py        # Pydantic model for LLM output
└── claude_client.py  # LLM reasoning call
```

### Modified Files

| File | Change |
|---|---|
| `audits/tasks.py` | Add `generate_recommendations` Celery task; call `.delay()` at end of `run_audit` |
| `audits/serializers.py` | Add `RecommendationSerializer` |
| `audits/views.py` | Add `RecommendationListView` |
| `audits/urls.py` | Wire `GET /api/audits/<pk>/recommendations/` |

### New Test Files

- `audits/tests/test_decision_rules.py`
- `audits/tests/test_decision_claude_client.py`
- `audits/tests/test_generate_recommendations_task.py`

---

## Component Details

### `rules.py` — `apply_priority_rules(issues, report)`

**Signature:**
```python
def apply_priority_rules(
    issues: list[AuditIssue],
    report: AuditReport,
) -> list[tuple[AuditIssue, str]]:
```

Returns `(issue, tier_label)` tuples sorted blocker → warning → info. Within each tier, ordered by `issue.score` ascending (worst score first).

**Tier assignment logic:**

| Condition | Tier |
|---|---|
| `issue.severity == 'critical'` | `blocker` |
| `issue.parameter_key in {'https', 'broken_links'}` | `blocker` |
| Category score for `issue.category` < 40 | `blocker` |
| `issue.severity == 'warning'` | `warning` |
| `issue.severity == 'info'` | `info` |

Category scores are read from the `report` object (`report.seo_score`, `report.conversion_score`, etc.) via a mapping dict.

---

### `schemas.py` — `RecommendationResult`

```python
from typing import Literal
from pydantic import BaseModel

class RecommendationResult(BaseModel):
    issue_id: int
    title: str
    effort: Literal['low', 'medium', 'high']
    impact: Literal['low', 'medium', 'high']
    priority_score: float   # 0.0–10.0, assigned by Claude
    rationale: str          # one sentence grounded in RAG context
```

---

### `claude_client.py` — `generate_recommendations_with_claude`

**Signature:**
```python
def generate_recommendations_with_claude(
    ranked_issues_with_context: list[dict],
    prompt_version: str = 'v1',
) -> list[RecommendationResult]:
```

**Input shape** (one dict per issue):
```python
{
    'issue_id': int,
    'tier': str,               # 'blocker' | 'warning' | 'info'
    'category': str,
    'severity': str,
    'title': str,
    'description': str,
    'parameter_key': str,
    'score': int,
    'rag_context': [           # top-3 KnowledgeDoc excerpts (first 300 chars of content)
        {'title': str, 'content': str},
        ...
    ],
}
```

**LLM call:**
- Model: `claude-sonnet-4-6`
- `tool_use` with `tool_choice={'type': 'tool', 'name': 'submit_recommendations'}`
- Max tokens: 2048
- Retries: up to 3 (same pattern as `scorers/claude_client.py`)
- Logging: model, input_tokens, output_tokens, latency_ms, cost_usd, prompt_version, attempt, success

**Tool definition schema:**
```json
{
  "name": "submit_recommendations",
  "input_schema": {
    "type": "object",
    "properties": {
      "recommendations": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "issue_id":       {"type": "integer"},
            "title":          {"type": "string"},
            "effort":         {"type": "string", "enum": ["low", "medium", "high"]},
            "impact":         {"type": "string", "enum": ["low", "medium", "high"]},
            "priority_score": {"type": "number", "minimum": 0, "maximum": 10},
            "rationale":      {"type": "string"}
          },
          "required": ["issue_id", "title", "effort", "impact", "priority_score", "rationale"]
        }
      }
    },
    "required": ["recommendations"]
  }
}
```

**Fallback:** On 3 consecutive failures, log the error and return `[]`. Do not raise — the audit is already `complete` and a missing recommendations list is preferable to marking the job `failed`.

**Prompt structure:**
```
You are an expert business website consultant.

Below is a prioritized list of issues found during a website audit,
along with relevant best-practice context for each issue.

For each issue, produce one recommendation with:
- A clear action title
- Effort estimate (low/medium/high)
- Impact estimate (low/medium/high)
- Priority score (0–10, higher = more urgent)
- A one-sentence rationale that cites the provided context

Issues:
[for each issue]
  [TIER: blocker|warning|info] <title> (<category>, score: <score>/10)
  Description: <description>
  Best-practice context:
    - <rag_doc_1_title>: <rag_doc_1_excerpt>
    - <rag_doc_2_title>: <rag_doc_2_excerpt>
    - <rag_doc_3_title>: <rag_doc_3_excerpt>
```

---

### `generate_recommendations` Celery Task

**Location:** `audits/tasks.py`

**Steps:**
1. Load `AuditReport` and all `AuditIssue` records for the job
2. Call `apply_priority_rules(issues, report)` → sorted `(issue, tier)` list
3. For each issue: call `retrieve_similar_docs(issue.description, top_k=3)` → per-issue RAG context
4. Build `ranked_issues_with_context` list
5. Call `generate_recommendations_with_claude(ranked_issues_with_context)`
6. Bulk-create `Recommendation` records (one per `RecommendationResult`)

**Error handling:** Wrap entire body in `try/except`. On failure, log the error. Do **not** update `AuditJob.status` — the job is already `complete` by the time this task runs.

**Handoff from `run_audit`:** At the end of the success path in `run_audit` (after `job.status = 'complete'`), add:
```python
generate_recommendations.delay(audit_job_id)
```

---

## API

### `GET /api/audits/<audit_job_id>/recommendations/`

**View:** `RecommendationListView(generics.ListAPIView)`  
**Serializer:** `RecommendationSerializer`  
**Ordering:** `-priority_score` (default `Meta.ordering` on `Recommendation` model)

**Response shape:**
```json
[
  {
    "id": 1,
    "issue_id": 12,
    "priority_score": 9.2,
    "effort": "low",
    "impact": "high",
    "title": "Enable HTTPS across all pages",
    "rationale": "Sites without HTTPS lose Google ranking signals and trigger browser security warnings, directly reducing trust and conversion.",
    "created_at": "2026-05-07T10:00:00Z"
  }
]
```

Returns `[]` if recommendations have not yet been generated (task still running or failed silently).

---

## Data Flow

```
run_audit completes
    │
    ├─ AuditReport saved
    ├─ AuditIssue records saved
    ├─ job.status = 'complete'
    └─ generate_recommendations.delay(audit_job_id)
            │
            ├─ apply_priority_rules() → sorted (issue, tier) list
            ├─ retrieve_similar_docs() × N issues → RAG context
            ├─ generate_recommendations_with_claude() → RecommendationResult list
            └─ Recommendation.objects.bulk_create()
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `AuditReport` not found | Log error, return early — no crash |
| `retrieve_similar_docs` fails for one issue | Log warning, include issue with empty `rag_context` |
| All 3 LLM retries fail | Log error, return `[]` — job stays `complete` |
| `bulk_create` fails | Log error — job stays `complete` |

---

## Testing Strategy

- **`test_decision_rules.py`** — unit tests for `apply_priority_rules`: verify tier assignment for critical issues, blocker parameter keys, low category scores, and correct within-tier ordering
- **`test_decision_claude_client.py`** — mock the Anthropic client; verify tool call structure, Pydantic validation, retry behaviour, and fallback to `[]`
- **`test_generate_recommendations_task.py`** — mock `retrieve_similar_docs` and `generate_recommendations_with_claude`; verify Recommendation records are created with correct fields; verify task survives LLM failure without changing job status
