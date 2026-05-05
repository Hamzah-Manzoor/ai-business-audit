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
