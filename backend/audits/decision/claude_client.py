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
